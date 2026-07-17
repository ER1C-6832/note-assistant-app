"""Optional native AEC and sherpa-onnx KWS probes for Gate 6.0.

Imports are lazy and every API is probe-only.  No model is downloaded and no
raw audio is persisted.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .gate6_contracts import MicrophoneOwner, PublicAudioFormat
from .gate6_probe import ProbeResourceTracker, process_runtime_sample
from .gate6_pyaudio_probe import (
    _LevelAccumulator,
    _load_pyaudio,
    _tone_frame,
)


class Gate60BackendUnavailable(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class AecAudioProcessingProbeAdapter:
    """Small reflective adapter for the optional aec-audio-processing wheel."""

    def __init__(self, sample_rate_hz: int = 16_000, channels: int = 1) -> None:
        try:
            from aec_audio_processing import AudioProcessor
        except ImportError as exc:
            raise Gate60BackendUnavailable(
                "aec_audio_processing_not_installed",
                "optional aec-audio-processing package is not installed",
            ) from exc
        try:
            self._processor = AudioProcessor(
                enable_aec=True,
                enable_ns=True,
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
            self._processor.set_stream_delay(50)
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
        }

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        close = getattr(self._processor, "close", None)
        if callable(close):
            close()


def run_live_aec_probe(
    *,
    scenario: str,
    duration_seconds: float = 4.0,
    input_device_index: int | None = None,
    output_device_index: int | None = None,
    sample_rate_hz: int = 16_000,
    channels: int = 1,
) -> dict[str, object]:
    if scenario not in {"far_end_only", "double_talk"}:
        raise ValueError("scenario must be far_end_only or double_talk")
    if not 1.0 <= duration_seconds <= 20.0:
        raise ValueError("duration_seconds must be between 1 and 20")
    audio_format = PublicAudioFormat(sample_rate_hz, channels, 2, 10)
    adapter = AecAudioProcessingProbeAdapter(sample_rate_hz, channels)
    pyaudio = _load_pyaudio()
    audio = pyaudio.PyAudio()
    tracker = ProbeResourceTracker()
    tracker.set_owner(MicrophoneOwner.BARGE_IN_MONITOR)
    backend_capabilities = adapter.capabilities()
    processor_lock = threading.Lock()
    stop_event = threading.Event()
    raw_levels = _LevelAccumulator()
    processed_levels = _LevelAccumulator()
    render_frames = 0
    processed_vad_trigger_count = 0
    errors: list[str] = []
    input_stream: Any | None = None
    output_stream: Any | None = None
    threads: list[threading.Thread] = []

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
        tracker.increment("processing_workers")

        def render_main() -> None:
            nonlocal render_frames
            name = threading.current_thread().name
            tracker.add_thread(name)
            sequence = 0
            try:
                while not stop_event.is_set():
                    raw = _tone_frame(audio_format, sequence, 550.0)
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
                    processed_vad_trigger_count += int(has_voice is True)
            except Exception as exc:
                errors.append(f"capture_failed:{type(exc).__name__}")
                stop_event.set()
            finally:
                tracker.remove_thread(name)

        input_stream.start_stream()
        output_stream.start_stream()
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
        adapter.close()
        audio.terminate()

    terminal = tracker.terminal_dict()
    return {
        "status": (
            "probe_complete" if not errors and tracker.is_terminal_zero() else "probe_failed"
        ),
        "scenario": scenario,
        "instruction": (
            "keep quiet while the test tone plays"
            if scenario == "far_end_only"
            else "say the prompted short phrase while the test tone plays"
        ),
        "input_public_name": (
            str(input_info.get("name", "input"))[:120] if "input_info" in locals() else None
        ),
        "output_public_name": (
            str(output_info.get("name", "output"))[:120] if "output_info" in locals() else None
        ),
        "audio_format": audio_format.public_dict(),
        "backend": backend_capabilities,
        "render_frames": render_frames,
        "capture_frames": raw_levels.frame_count,
        "processed_frames": processed_levels.frame_count,
        "raw_level_summary": raw_levels.public_dict(),
        "processed_level_summary": processed_levels.public_dict(),
        "processed_vad_trigger_count": processed_vad_trigger_count,
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
) -> dict[str, object]:
    if not 2.0 <= duration_seconds <= 60.0:
        raise ValueError("duration_seconds must be between 2 and 60")
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
    started_ns = time.perf_counter_ns()
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
                            "detected_after_ms": round((now_ns - started_ns) / 1_000_000, 3),
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
    return {
        "status": (
            "probe_complete" if not errors and tracker.is_terminal_zero() else "probe_failed"
        ),
        "engine": "sherpa-onnx KeywordSpotter",
        "model": model.public_dict(),
        "input_public_name": (
            str(input_info.get("name", "input"))[:120] if "input_info" in locals() else None
        ),
        "load_ms": load_ms,
        "duration_ms": round((time.perf_counter_ns() - started_ns) / 1_000_000, 3),
        "microphone_frames": frames,
        "hits": hits,
        "hit_count": len(hits),
        "duplicate_cooldown_count": duplicate_cooldown_count,
        "cooldown_ms": cooldown_ms,
        "runtime_sample": process_runtime_sample(),
        "errors": errors,
        "terminal": terminal,
        "pcm_persisted": False,
        "idle_microphone_uploaded_frames": 0,
    }
