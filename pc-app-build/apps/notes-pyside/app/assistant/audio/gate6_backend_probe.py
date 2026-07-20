"""Optional native AEC and sherpa-onnx KWS probes for Gate 6.0.

Imports are lazy and every API is probe-only.  No model is downloaded and no
raw audio is persisted.
"""

from __future__ import annotations

import math
import statistics
import struct
import threading
import time
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .gate6_contracts import MicrophoneOwner, PublicAudioFormat
from .gate6_probe import ProbeResourceTracker, process_runtime_sample
from .gate6_pyaudio_probe import (
    _LevelAccumulator,
    _load_pyaudio,
)


class Gate60BackendUnavailable(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class AecAudioProcessingProbeAdapter:
    """Small reflective adapter for the optional aec-audio-processing wheel."""

    def __init__(
        self,
        sample_rate_hz: int = 16_000,
        channels: int = 1,
        *,
        enable_aec: bool = True,
        enable_ns: bool = True,
        stream_delay_ms: int = 100,
    ) -> None:
        try:
            from aec_audio_processing import AudioProcessor
        except ImportError as exc:
            raise Gate60BackendUnavailable(
                "aec_audio_processing_not_installed",
                "optional aec-audio-processing package is not installed",
            ) from exc
        try:
            self._processor = AudioProcessor(
                enable_aec=enable_aec,
                enable_ns=enable_ns,
                enable_agc=False,
                enable_vad=True,
            )
            try:
                self._processor.set_stream_format(
                    sample_rate_in=sample_rate_hz,
                    channel_count_in=channels,
                    sample_rate_out=sample_rate_hz,
                    channel_count_out=channels,
                )
            except TypeError:
                self._processor.set_stream_format(sample_rate_hz, channels)
            self._processor.set_reverse_stream_format(sample_rate_hz, channels)
            self._processor.set_stream_delay(stream_delay_ms)
        except Exception as exc:
            raise Gate60BackendUnavailable(
                "aec_backend_create_failed",
                f"AEC backend could not be initialized: {type(exc).__name__}",
            ) from exc
        self._reverse_method = next(
            (
                getattr(self._processor, name)
                for name in (
                    "process_reverse_stream",
                    "process_reverse",
                    "analyze_reverse_stream",
                    "process_render",
                )
                if callable(getattr(self._processor, name, None))
            ),
            None,
        )
        if self._reverse_method is None:
            raise Gate60BackendUnavailable(
                "aec_reverse_stream_api_missing",
                "AEC backend does not expose a reverse/render stream method",
            )
        self._closed = False
        self._requested_aec = enable_aec
        self._requested_ns = enable_ns
        self._stream_delay_ms = stream_delay_ms

    @property
    def public_name(self) -> str:
        return "aec-audio-processing/WebRTC APM"

    def process_render(self, pcm16_le: bytes) -> None:
        if self._closed:
            raise RuntimeError("AEC adapter is closed")
        self._reverse_method(pcm16_le)

    def process_capture(self, pcm16_le: bytes) -> bytes:
        if self._closed:
            raise RuntimeError("AEC adapter is closed")
        output = self._processor.process_stream(pcm16_le)
        return bytes(output)

    def has_voice(self) -> bool | None:
        method = getattr(self._processor, "has_voice", None)
        if not callable(method):
            return None
        try:
            return bool(method())
        except Exception:
            return None

    def capabilities(self) -> dict[str, object]:
        def effective(name: str) -> bool | None:
            method = getattr(self._processor, name, None)
            if not callable(method):
                return None
            try:
                return bool(method())
            except Exception:
                return None

        return {
            "backend_public_name": self.public_name,
            "aec_enabled": effective("aec_enabled"),
            "ns_enabled": effective("ns_enabled"),
            "agc_enabled": effective("agc_enabled"),
            "vad_enabled": effective("vad_enabled"),
            "reverse_stream_api": getattr(self._reverse_method, "__name__", "available"),
            "internal_block_ms": 10,
            "requested_aec": self._requested_aec,
            "requested_ns": self._requested_ns,
            "requested_agc": False,
            "stream_delay_ms": self._stream_delay_ms,
        }

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        close = getattr(self._processor, "close", None)
        if callable(close):
            close()


def resolve_stream_delay_ms(
    *,
    requested_delay_ms: int | None,
    input_latency_seconds: float | None,
    output_latency_seconds: float | None,
) -> tuple[int, str]:
    """Resolve a bounded APM delay without freezing one machine's 50 ms guess."""

    if requested_delay_ms is not None:
        if not 0 <= requested_delay_ms <= 500:
            raise ValueError("stream delay must be between 0 and 500 ms")
        return int(requested_delay_ms), "explicit"
    latencies = [
        float(item)
        for item in (input_latency_seconds, output_latency_seconds)
        if item is not None and math.isfinite(float(item)) and float(item) >= 0
    ]
    if not latencies:
        return 100, "fallback"
    return min(500, max(0, round(sum(latencies) * 1000))), "stream_reported"


def _level(summary: dict[str, object], key: str) -> float:
    value = summary.get(key, 0.0)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def _attenuation_db(raw_rms: float, processed_rms: float) -> float | None:
    if raw_rms <= 0:
        return None
    return round(20.0 * math.log10(raw_rms / max(processed_rms, 1.0)), 3)


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(item) for item in values)
    position = (len(ordered) - 1) * percentile / 100.0
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 3)
    weight = position - lower
    return round(ordered[lower] * (1.0 - weight) + ordered[upper] * weight, 3)


def _longest_active_run(flags: Sequence[bool]) -> int:
    longest = 0
    current = 0
    for active in flags:
        current = current + 1 if active else 0
        longest = max(longest, current)
    return longest


def _summary_with_percentiles(
    summary: dict[str, object], rms_values: Sequence[float]
) -> dict[str, object]:
    return {
        **summary,
        "rms_p75": _percentile(rms_values, 75.0),
        "rms_p90": _percentile(rms_values, 90.0),
        "rms_p95": _percentile(rms_values, 95.0),
    }


def analyze_double_talk_activity(
    *,
    raw_baseline_rms: Sequence[float],
    processed_baseline_rms: Sequence[float],
    raw_speech_rms: Sequence[float],
    processed_speech_rms: Sequence[float],
) -> dict[str, object]:
    """Detect short near-end bursts and compare aligned processed frames."""

    aligned_count = min(len(raw_speech_rms), len(processed_speech_rms))
    raw_speech = [float(item) for item in list(raw_speech_rms)[:aligned_count]]
    processed_speech = [float(item) for item in list(processed_speech_rms)[:aligned_count]]
    raw_baseline_median = _percentile(raw_baseline_rms, 50.0)
    raw_baseline_p95 = _percentile(raw_baseline_rms, 95.0)
    processed_baseline_median = _percentile(processed_baseline_rms, 50.0)
    processed_baseline_p95 = _percentile(processed_baseline_rms, 95.0)
    raw_activity_threshold = max(
        raw_baseline_p95 * 1.10,
        raw_baseline_median * 1.25,
        raw_baseline_median + 8.0,
    )
    processed_activity_threshold = max(
        processed_baseline_p95 * 1.05,
        processed_baseline_median * 1.20,
        processed_baseline_median + 0.75,
    )
    raw_flags = [item >= raw_activity_threshold for item in raw_speech]
    raw_active_indices = [index for index, active in enumerate(raw_flags) if active]
    raw_active_frames = len(raw_active_indices)
    raw_longest_run = _longest_active_run(raw_flags)
    raw_near_speech_observed = raw_active_frames >= 5 and raw_longest_run >= 3

    processed_on_raw_flags = [
        raw_flags[index] and processed_speech[index] >= processed_activity_threshold
        for index in range(aligned_count)
    ]
    processed_active_on_raw_frames = sum(processed_on_raw_flags)
    processed_on_raw_active_ratio = round(
        processed_active_on_raw_frames / max(raw_active_frames, 1), 4
    )
    processed_longest_aligned_run = _longest_active_run(processed_on_raw_flags)

    raw_active_lifts = [
        max(0.0, raw_speech[index] - raw_baseline_median) for index in raw_active_indices
    ]
    processed_active_lifts = [
        max(0.0, processed_speech[index] - processed_baseline_median)
        for index in raw_active_indices
    ]
    raw_active_lift_median = float(statistics.median(raw_active_lifts)) if raw_active_lifts else 0.0
    processed_active_lift_median = (
        float(statistics.median(processed_active_lifts)) if processed_active_lifts else 0.0
    )
    retention_ratio = round(processed_active_lift_median / max(raw_active_lift_median, 1.0), 4)
    processed_near_speech_observed = (
        raw_near_speech_observed
        and processed_active_on_raw_frames >= 3
        and processed_longest_aligned_run >= 2
        and processed_on_raw_active_ratio >= 0.10
    )
    near_end_preserved = processed_near_speech_observed and retention_ratio >= 0.03
    return {
        "analysis_method": "aligned_short_utterance_activity_v2",
        "aligned_speech_frames": aligned_count,
        "raw_baseline_rms_median": raw_baseline_median,
        "raw_baseline_rms_p95": raw_baseline_p95,
        "raw_speech_rms_p90": _percentile(raw_speech, 90.0),
        "raw_speech_rms_p95": _percentile(raw_speech, 95.0),
        "raw_activity_threshold": round(raw_activity_threshold, 3),
        "raw_active_frames": raw_active_frames,
        "raw_active_frame_ratio": round(raw_active_frames / max(aligned_count, 1), 4),
        "raw_longest_active_run_frames": raw_longest_run,
        "raw_near_speech_observed": raw_near_speech_observed,
        "processed_baseline_rms_median": processed_baseline_median,
        "processed_baseline_rms_p95": processed_baseline_p95,
        "processed_speech_rms_p90": _percentile(processed_speech, 90.0),
        "processed_speech_rms_p95": _percentile(processed_speech, 95.0),
        "processed_activity_threshold": round(processed_activity_threshold, 3),
        "processed_active_on_raw_frames": processed_active_on_raw_frames,
        "processed_on_raw_active_ratio": processed_on_raw_active_ratio,
        "processed_longest_aligned_run_frames": processed_longest_aligned_run,
        "processed_near_speech_observed": processed_near_speech_observed,
        "raw_active_lift_median": round(raw_active_lift_median, 3),
        "processed_active_lift_median": round(processed_active_lift_median, 3),
        "near_end_retention_ratio": retention_ratio,
        "minimum_near_end_retention_ratio": 0.03,
        "near_end_preserved": near_end_preserved,
    }


def _speech_like_reference_frame(audio_format: PublicAudioFormat, sequence: int) -> bytes:
    """Generate a bounded speech-like render reference without persisting a fixture."""

    samples: list[int] = []
    start = sequence * audio_format.samples_per_frame
    for offset in range(audio_format.samples_per_frame):
        sample_index = start + offset
        seconds = sample_index / audio_format.sample_rate_hz
        syllable_envelope = 0.2 + 0.8 * abs(math.sin(2.0 * math.pi * 3.2 * seconds))
        carrier = (
            math.sin(2.0 * math.pi * 180.0 * seconds)
            + 0.55 * math.sin(2.0 * math.pi * 620.0 * seconds)
            + 0.3 * math.sin(2.0 * math.pi * 1_450.0 * seconds)
            + 0.15 * math.sin(2.0 * math.pi * 2_300.0 * seconds)
        )
        value = max(-32760, min(32760, round(620 * syllable_envelope * carrier)))
        samples.extend([value] * audio_format.channels)
    return struct.pack("<" + "h" * len(samples), *samples)


def evaluate_aec_probe(
    *,
    scenario: str,
    duration_seconds: float,
    render_frames: int,
    raw_summary: dict[str, object],
    processed_summary: dict[str, object],
    raw_baseline_summary: dict[str, object] | None,
    processed_baseline_summary: dict[str, object] | None,
    raw_speech_summary: dict[str, object] | None,
    processed_speech_summary: dict[str, object] | None,
    double_talk_activity: dict[str, object] | None,
    errors: list[str],
    terminal_zero: bool,
) -> dict[str, object]:
    """Apply semantic AEC acceptance; process completion alone is not success."""

    reasons: list[str] = []
    expected_frames = max(1, round(duration_seconds * 100))
    capture_frames = int(raw_summary.get("frame_count", 0) or 0)
    processed_frames = int(processed_summary.get("frame_count", 0) or 0)
    enough_frames = min(render_frames, capture_frames, processed_frames) >= expected_frames * 0.8
    if errors:
        reasons.append("native_or_resource_error")
    if not terminal_zero:
        reasons.append("terminal_resources_not_zero")
    if not enough_frames:
        reasons.append("insufficient_frames")

    raw_rms = _level(raw_summary, "rms_median")
    processed_rms = _level(processed_summary, "rms_median")
    attenuation_db = _attenuation_db(raw_rms, processed_rms)
    criteria: dict[str, object] = {
        "expected_frames": expected_frames,
        "enough_frames": enough_frames,
        "echo_attenuation_db": attenuation_db,
    }

    if scenario == "far_end_only":
        far_end_observed = raw_rms >= 20.0
        echo_suppressed = attenuation_db is not None and attenuation_db >= 6.0
        criteria.update(
            {
                "far_end_observed": far_end_observed,
                "minimum_echo_attenuation_db": 6.0,
                "echo_suppressed": echo_suppressed,
            }
        )
        if not far_end_observed:
            reasons.append("far_end_not_observed_at_microphone")
        if not echo_suppressed:
            reasons.append("echo_attenuation_below_budget")
    else:
        activity = double_talk_activity or {}
        raw_near_speech_observed = activity.get("raw_near_speech_observed") is True
        processed_near_speech_observed = activity.get("processed_near_speech_observed") is True
        near_end_preserved = activity.get("near_end_preserved") is True
        criteria.update(
            {
                "raw_near_speech_observed": raw_near_speech_observed,
                "processed_near_speech_observed": processed_near_speech_observed,
                "near_end_retention_ratio": activity.get("near_end_retention_ratio", 0.0),
                "minimum_near_end_retention_ratio": 0.03,
                "near_end_preserved": near_end_preserved,
                "short_utterance_activity": activity,
            }
        )
        if not activity:
            reasons.append("double_talk_activity_missing")
        elif not raw_near_speech_observed:
            reasons.append("user_speech_not_observed")
        elif not near_end_preserved:
            reasons.append("near_end_speech_not_preserved")

    accepted = not reasons
    failure_code = None
    if not accepted:
        if "near_end_speech_not_preserved" in reasons:
            failure_code = "aec_near_end_not_preserved"
        elif "user_speech_not_observed" in reasons:
            failure_code = "aec_user_speech_not_observed"
        elif "far_end_not_observed_at_microphone" in reasons:
            failure_code = "aec_far_end_not_observed"
        elif "echo_attenuation_below_budget" in reasons:
            failure_code = "aec_echo_attenuation_insufficient"
        else:
            failure_code = "aec_probe_runtime_failed"
    return {
        "accepted": accepted,
        "semantic_status": "accepted" if accepted else "inconclusive",
        "failure_code": failure_code,
        "reasons": reasons,
        "criteria": criteria,
    }


def run_live_aec_probe(
    *,
    scenario: str,
    duration_seconds: float = 4.0,
    input_device_index: int | None = None,
    output_device_index: int | None = None,
    sample_rate_hz: int = 16_000,
    channels: int = 1,
    stream_delay_ms: int | None = None,
    processing_mode: str = "aec_only",
    speech_start_delay_seconds: float = 1.5,
) -> dict[str, object]:
    if scenario not in {"far_end_only", "double_talk"}:
        raise ValueError("scenario must be far_end_only or double_talk")
    if not 1.0 <= duration_seconds <= 20.0:
        raise ValueError("duration_seconds must be between 1 and 20")
    if processing_mode not in {"aec_only", "aec_ns", "ns_only"}:
        raise ValueError("processing_mode must be aec_only, aec_ns, or ns_only")
    if scenario == "double_talk" and not 0.5 <= speech_start_delay_seconds <= 5.0:
        raise ValueError("speech start delay must be between 0.5 and 5 seconds")
    if scenario == "double_talk" and duration_seconds < speech_start_delay_seconds + 2.0:
        raise ValueError("double-talk duration must leave at least 2 seconds for speech")
    audio_format = PublicAudioFormat(sample_rate_hz, channels, 2, 10)
    pyaudio = _load_pyaudio()
    audio = pyaudio.PyAudio()
    tracker = ProbeResourceTracker()
    tracker.set_owner(MicrophoneOwner.BARGE_IN_MONITOR)
    adapter: AecAudioProcessingProbeAdapter | None = None
    backend_capabilities: dict[str, object] = {}
    processor_lock = threading.Lock()
    stop_event = threading.Event()
    raw_levels = _LevelAccumulator()
    processed_levels = _LevelAccumulator()
    raw_baseline_levels = _LevelAccumulator()
    processed_baseline_levels = _LevelAccumulator()
    raw_speech_levels = _LevelAccumulator()
    processed_speech_levels = _LevelAccumulator()
    raw_baseline_rms_values: deque[float] = deque(maxlen=2_048)
    processed_baseline_rms_values: deque[float] = deque(maxlen=2_048)
    raw_speech_rms_values: deque[float] = deque(maxlen=2_048)
    processed_speech_rms_values: deque[float] = deque(maxlen=2_048)
    render_frames = 0
    processed_vad_trigger_count = 0
    errors: list[str] = []
    input_stream: Any | None = None
    output_stream: Any | None = None
    threads: list[threading.Thread] = []
    measurement_started_ns: int | None = None
    resolved_delay_ms: int | None = None
    delay_source: str | None = None

    try:
        if input_device_index is None:
            input_info = audio.get_default_input_device_info()
            input_device_index = int(input_info["index"])
        else:
            input_info = audio.get_device_info_by_index(input_device_index)
        if output_device_index is None:
            output_info = audio.get_default_output_device_info()
            output_device_index = int(output_info["index"])
        else:
            output_info = audio.get_device_info_by_index(output_device_index)
        input_stream = audio.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=sample_rate_hz,
            input=True,
            input_device_index=input_device_index,
            frames_per_buffer=audio_format.samples_per_frame,
            start=False,
        )
        tracker.increment("capture_streams")
        output_stream = audio.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=sample_rate_hz,
            output=True,
            output_device_index=output_device_index,
            frames_per_buffer=audio_format.samples_per_frame,
            start=False,
        )
        tracker.increment("output_streams")
        tracker.increment("duplex_sessions")
        resolved_delay_ms, delay_source = resolve_stream_delay_ms(
            requested_delay_ms=stream_delay_ms,
            input_latency_seconds=float(input_stream.get_input_latency()),
            output_latency_seconds=float(output_stream.get_output_latency()),
        )
        adapter = AecAudioProcessingProbeAdapter(
            sample_rate_hz,
            channels,
            enable_aec=processing_mode != "ns_only",
            enable_ns=processing_mode != "aec_only",
            stream_delay_ms=resolved_delay_ms,
        )
        backend_capabilities = adapter.capabilities()
        tracker.increment("processing_workers")

        def render_main() -> None:
            nonlocal render_frames
            name = threading.current_thread().name
            tracker.add_thread(name)
            sequence = 0
            try:
                while not stop_event.is_set():
                    raw = _speech_like_reference_frame(audio_format, sequence)
                    with processor_lock:
                        adapter.process_render(raw)
                    output_stream.write(raw)
                    sequence += 1
                    render_frames += 1
            except Exception as exc:
                errors.append(f"render_failed:{type(exc).__name__}")
                stop_event.set()
            finally:
                tracker.remove_thread(name)

        def capture_main() -> None:
            nonlocal processed_vad_trigger_count
            name = threading.current_thread().name
            tracker.add_thread(name)
            try:
                while not stop_event.is_set():
                    raw = bytes(
                        input_stream.read(
                            audio_format.samples_per_frame,
                            exception_on_overflow=False,
                        )
                    )
                    stamp = time.perf_counter_ns()
                    raw_levels.accept(raw, stamp)
                    with processor_lock:
                        processed = adapter.process_capture(raw)
                        has_voice = adapter.has_voice()
                    processed_levels.accept(processed, stamp)
                    if scenario == "double_talk" and measurement_started_ns is not None:
                        elapsed_seconds = (stamp - measurement_started_ns) / 1_000_000_000
                        if elapsed_seconds < speech_start_delay_seconds:
                            raw_baseline_levels.accept(raw, stamp)
                            processed_baseline_levels.accept(processed, stamp)
                            raw_baseline_rms_values.append(raw_levels.rms_values[-1])
                            processed_baseline_rms_values.append(processed_levels.rms_values[-1])
                        else:
                            raw_speech_levels.accept(raw, stamp)
                            processed_speech_levels.accept(processed, stamp)
                            raw_speech_rms_values.append(raw_levels.rms_values[-1])
                            processed_speech_rms_values.append(processed_levels.rms_values[-1])
                    processed_vad_trigger_count += int(has_voice is True)
            except Exception as exc:
                errors.append(f"capture_failed:{type(exc).__name__}")
                stop_event.set()
            finally:
                tracker.remove_thread(name)

        input_stream.start_stream()
        output_stream.start_stream()
        measurement_started_ns = time.perf_counter_ns()
        threads = [
            threading.Thread(target=render_main, name="gate6-aec-render", daemon=False),
            threading.Thread(target=capture_main, name="gate6-aec-capture", daemon=False),
        ]
        for thread in threads:
            thread.start()
        stop_event.wait(duration_seconds)
    finally:
        stop_event.set()
        for thread in threads:
            thread.join(timeout=2.0)
            if thread.is_alive():
                errors.append(f"thread_stop_timeout:{thread.name}")
        for stream, counter in (
            (input_stream, "capture_streams"),
            (output_stream, "output_streams"),
        ):
            if stream is not None:
                try:
                    if stream.is_active():
                        stream.stop_stream()
                    stream.close()
                except Exception as exc:
                    errors.append(f"stream_close_failed:{type(exc).__name__}")
                finally:
                    if getattr(tracker, counter):
                        tracker.decrement(counter)
        if tracker.processing_workers:
            tracker.decrement("processing_workers")
        if tracker.duplex_sessions:
            tracker.decrement("duplex_sessions")
        tracker.release_owner(MicrophoneOwner.BARGE_IN_MONITOR)
        if adapter is not None:
            adapter.close()
        audio.terminate()

    terminal = tracker.terminal_dict()
    raw_summary = _summary_with_percentiles(raw_levels.public_dict(), raw_levels.rms_values)
    processed_summary = _summary_with_percentiles(
        processed_levels.public_dict(), processed_levels.rms_values
    )
    raw_baseline_summary = _summary_with_percentiles(
        raw_baseline_levels.public_dict(), raw_baseline_rms_values
    )
    processed_baseline_summary = _summary_with_percentiles(
        processed_baseline_levels.public_dict(), processed_baseline_rms_values
    )
    raw_speech_summary = _summary_with_percentiles(
        raw_speech_levels.public_dict(), raw_speech_rms_values
    )
    processed_speech_summary = _summary_with_percentiles(
        processed_speech_levels.public_dict(), processed_speech_rms_values
    )
    double_talk_activity = (
        analyze_double_talk_activity(
            raw_baseline_rms=raw_baseline_rms_values,
            processed_baseline_rms=processed_baseline_rms_values,
            raw_speech_rms=raw_speech_rms_values,
            processed_speech_rms=processed_speech_rms_values,
        )
        if scenario == "double_talk"
        else None
    )
    acceptance = evaluate_aec_probe(
        scenario=scenario,
        duration_seconds=duration_seconds,
        render_frames=render_frames,
        raw_summary=raw_summary,
        processed_summary=processed_summary,
        raw_baseline_summary=raw_baseline_summary,
        processed_baseline_summary=processed_baseline_summary,
        raw_speech_summary=raw_speech_summary,
        processed_speech_summary=processed_speech_summary,
        double_talk_activity=double_talk_activity,
        errors=errors,
        terminal_zero=tracker.is_terminal_zero(),
    )
    return {
        "status": (
            "probe_failed"
            if errors or not tracker.is_terminal_zero()
            else ("probe_complete" if acceptance["accepted"] else "probe_inconclusive")
        ),
        "scenario": scenario,
        "instruction": (
            "keep quiet while the test tone plays"
            if scenario == "far_end_only"
            else "keep quiet during lead-in, then say several natural short phrases"
        ),
        "input_public_name": (
            str(input_info.get("name", "input"))[:120] if "input_info" in locals() else None
        ),
        "output_public_name": (
            str(output_info.get("name", "output"))[:120] if "output_info" in locals() else None
        ),
        "audio_format": audio_format.public_dict(),
        "backend": backend_capabilities,
        "render_reference_type": "deterministic_speech_like",
        "processing_mode": processing_mode,
        "stream_delay_ms": resolved_delay_ms,
        "stream_delay_source": delay_source,
        "speech_start_delay_ms": (
            round(speech_start_delay_seconds * 1000) if scenario == "double_talk" else None
        ),
        "render_frames": render_frames,
        "capture_frames": raw_levels.frame_count,
        "processed_frames": processed_levels.frame_count,
        "raw_level_summary": raw_summary,
        "processed_level_summary": processed_summary,
        "raw_baseline_level_summary": raw_baseline_summary,
        "processed_baseline_level_summary": processed_baseline_summary,
        "raw_speech_level_summary": raw_speech_summary,
        "processed_speech_level_summary": processed_speech_summary,
        "processed_vad_trigger_count": processed_vad_trigger_count,
        "backend_vad_is_diagnostic_only": True,
        "acceptance": acceptance,
        "product_uplink_frames": 0,
        "errors": errors,
        "terminal": terminal,
        "runtime_sample": process_runtime_sample(),
        "pcm_persisted": False,
    }


@dataclass(frozen=True, slots=True)
class SherpaKwsModelPaths:
    tokens: Path
    encoder: Path
    decoder: Path
    joiner: Path
    keywords_file: Path

    def validate(self) -> None:
        missing = [path.name for path in self.as_tuple() if not path.is_file()]
        if missing:
            raise Gate60BackendUnavailable(
                "kws_model_missing",
                "missing KWS model files: " + ", ".join(missing),
            )

    def as_tuple(self) -> tuple[Path, ...]:
        return self.tokens, self.encoder, self.decoder, self.joiner, self.keywords_file

    def public_dict(self) -> dict[str, object]:
        return {
            "tokens_public_name": self.tokens.name,
            "encoder_public_name": self.encoder.name,
            "decoder_public_name": self.decoder.name,
            "joiner_public_name": self.joiner.name,
            "keywords_public_name": self.keywords_file.name,
            "total_model_size_bytes": sum(path.stat().st_size for path in self.as_tuple()),
        }


def run_live_sherpa_kws_probe(
    *,
    model: SherpaKwsModelPaths,
    duration_seconds: float = 10.0,
    input_device_index: int | None = None,
    sample_rate_hz: int = 16_000,
    cooldown_ms: int = 1_500,
    required_hits: int = 2,
    ready_callback: Callable[[], None] | None = None,
) -> dict[str, object]:
    if not 2.0 <= duration_seconds <= 60.0:
        raise ValueError("duration_seconds must be between 2 and 60")
    if not 1 <= required_hits <= 10:
        raise ValueError("required_hits must be between 1 and 10")
    model.validate()
    try:
        import numpy as np
        import sherpa_onnx
    except ImportError as exc:
        raise Gate60BackendUnavailable(
            "sherpa_onnx_not_installed",
            "sherpa-onnx and numpy are required for the KWS probe",
        ) from exc
    pyaudio = _load_pyaudio()
    load_started = time.perf_counter_ns()
    try:
        spotter = sherpa_onnx.KeywordSpotter(
            tokens=str(model.tokens),
            encoder=str(model.encoder),
            decoder=str(model.decoder),
            joiner=str(model.joiner),
            keywords_file=str(model.keywords_file),
            num_threads=2,
            provider="cpu",
        )
        stream = spotter.create_stream()
    except Exception as exc:
        raise Gate60BackendUnavailable(
            "kws_model_load_failed",
            f"sherpa KWS model failed to load: {type(exc).__name__}",
        ) from exc
    load_ms = round((time.perf_counter_ns() - load_started) / 1_000_000, 3)
    audio = pyaudio.PyAudio()
    tracker = ProbeResourceTracker()
    tracker.set_owner(MicrophoneOwner.WAKEWORD_KWS)
    tracker.increment("kws_workers")
    hits: list[dict[str, object]] = []
    duplicate_cooldown_count = 0
    last_hit_ns: int | None = None
    input_stream: Any | None = None
    errors: list[str] = []
    started_ns: int | None = None
    frames = 0
    try:
        if input_device_index is None:
            input_info = audio.get_default_input_device_info()
            input_device_index = int(input_info["index"])
        else:
            input_info = audio.get_device_info_by_index(input_device_index)
        samples_per_frame = sample_rate_hz // 50
        input_stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate_hz,
            input=True,
            input_device_index=input_device_index,
            frames_per_buffer=samples_per_frame,
            start=True,
        )
        tracker.increment("capture_streams")
        if ready_callback is not None:
            ready_callback()
        started_ns = time.perf_counter_ns()
        deadline = time.monotonic() + duration_seconds
        while time.monotonic() < deadline:
            raw = bytes(input_stream.read(samples_per_frame, exception_on_overflow=False))
            frames += 1
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            stream.accept_waveform(sample_rate_hz, samples)
            while spotter.is_ready(stream):
                spotter.decode_stream(stream)
                result = str(spotter.get_result(stream) or "").strip()
                if not result:
                    continue
                now_ns = time.perf_counter_ns()
                if last_hit_ns is not None and now_ns - last_hit_ns < cooldown_ms * 1_000_000:
                    duplicate_cooldown_count += 1
                else:
                    hits.append(
                        {
                            "keyword_public_name": result[:120],
                            "detected_after_ms": round(
                                (now_ns - (started_ns or now_ns)) / 1_000_000, 3
                            ),
                        }
                    )
                    last_hit_ns = now_ns
                spotter.reset_stream(stream)
    except Exception as exc:
        errors.append(f"kws_live_failed:{type(exc).__name__}")
    finally:
        if input_stream is not None:
            try:
                if input_stream.is_active():
                    input_stream.stop_stream()
                input_stream.close()
            finally:
                if tracker.capture_streams:
                    tracker.decrement("capture_streams")
        audio.terminate()
        if tracker.kws_workers:
            tracker.decrement("kws_workers")
        tracker.release_owner(MicrophoneOwner.WAKEWORD_KWS)

    terminal = tracker.terminal_dict()
    runtime_ok = not errors and tracker.is_terminal_zero()
    hit_requirement_met = len(hits) >= required_hits
    acceptance = {
        "accepted": runtime_ok and hit_requirement_met,
        "required_distinct_hits": 2,
        "observed_distinct_hits": len(hits),
        "cooldown_ms": cooldown_ms,
        "failure_code": (
            None
            if runtime_ok and hit_requirement_met
            else ("kws_keyword_not_detected" if runtime_ok else "kws_probe_runtime_failed")
        ),
    }
    if required_hits != 2:
        acceptance["required_distinct_hits"] = required_hits
    return {
        "status": (
            "probe_complete"
            if acceptance["accepted"]
            else ("probe_inconclusive" if runtime_ok else "probe_failed")
        ),
        "engine": "sherpa-onnx KeywordSpotter",
        "model": model.public_dict(),
        "input_public_name": (
            str(input_info.get("name", "input"))[:120] if "input_info" in locals() else None
        ),
        "load_ms": load_ms,
        "duration_ms": (
            round((time.perf_counter_ns() - started_ns) / 1_000_000, 3)
            if started_ns is not None
            else 0.0
        ),
        "microphone_frames": frames,
        "hits": hits,
        "hit_count": len(hits),
        "duplicate_cooldown_count": duplicate_cooldown_count,
        "cooldown_ms": cooldown_ms,
        "acceptance": acceptance,
        "runtime_sample": process_runtime_sample(),
        "errors": errors,
        "terminal": terminal,
        "pcm_persisted": False,
        "idle_microphone_uploaded_frames": 0,
    }
