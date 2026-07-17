"""Isolated PyAudio inventory and duplex probes for Gate 6.0.

No captured or rendered PCM is persisted.  Real streams are opened only when a
probe CLI explicitly calls these functions; importing this module is inert.
"""

from __future__ import annotations

import math
import statistics
import struct
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from .gate6_contracts import AudioDeviceDescriptor, AudioPlatform, PublicAudioFormat
from .gate6_probe import (
    BoundedProbeQueue,
    ProbeQueueOverflow,
    ProbeResourceTracker,
    private_identifier_digest,
    process_runtime_sample,
    public_device_dict,
)


class Gate60PyAudioUnavailable(RuntimeError):
    pass


class Gate60DeviceProbeError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _load_pyaudio():
    try:
        import pyaudio
    except ImportError as exc:
        raise Gate60PyAudioUnavailable("PyAudio is not installed in this environment") from exc
    return pyaudio


def _platform_value() -> AudioPlatform:
    import platform

    value = platform.system().lower()
    if value == "windows":
        return AudioPlatform.WINDOWS
    if value == "darwin":
        return AudioPlatform.MACOS
    if value == "linux":
        return AudioPlatform.LINUX
    return AudioPlatform.OTHER


def _safe_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number, 6) if math.isfinite(number) else None


def _candidate_formats() -> tuple[PublicAudioFormat, ...]:
    return (
        PublicAudioFormat(16_000, 1, 2, 10),
        PublicAudioFormat(16_000, 1, 2, 20),
        PublicAudioFormat(48_000, 1, 2, 10),
        PublicAudioFormat(48_000, 2, 2, 10),
        PublicAudioFormat(48_000, 2, 2, 20),
    )


def enumerate_pyaudio_devices() -> dict[str, object]:
    pyaudio = _load_pyaudio()
    audio = pyaudio.PyAudio()
    try:
        host_apis: dict[int, str] = {}
        for index in range(int(audio.get_host_api_count())):
            info = audio.get_host_api_info_by_index(index)
            host_apis[index] = str(info.get("name") or f"host-api-{index}")[:80]
        try:
            default_input = int(audio.get_default_input_device_info()["index"])
        except (IOError, KeyError, TypeError, ValueError):
            default_input = -1
        try:
            default_output = int(audio.get_default_output_device_info()["index"])
        except (IOError, KeyError, TypeError, ValueError):
            default_output = -1

        devices: list[AudioDeviceDescriptor] = []
        format_checks: list[dict[str, object]] = []
        for index in range(int(audio.get_device_count())):
            info = audio.get_device_info_by_index(index)
            max_input = int(info.get("maxInputChannels", 0) or 0)
            max_output = int(info.get("maxOutputChannels", 0) or 0)
            if max_input <= 0 and max_output <= 0:
                continue
            host_index = int(info.get("hostApi", -1) or -1)
            public_name = str(info.get("name") or f"audio-device-{index}")[:120]
            private_key = f"pyaudio:{host_index}:{index}:{public_name}"
            supported: list[PublicAudioFormat] = []
            for candidate in _candidate_formats():
                input_ok = False
                output_ok = False
                if max_input >= candidate.channels:
                    try:
                        input_ok = bool(
                            audio.is_format_supported(
                                candidate.sample_rate_hz,
                                input_device=index,
                                input_channels=candidate.channels,
                                input_format=pyaudio.paInt16,
                            )
                        )
                    except (ValueError, OSError):
                        input_ok = False
                if max_output >= candidate.channels:
                    try:
                        output_ok = bool(
                            audio.is_format_supported(
                                candidate.sample_rate_hz,
                                output_device=index,
                                output_channels=candidate.channels,
                                output_format=pyaudio.paInt16,
                            )
                        )
                    except (ValueError, OSError):
                        output_ok = False
                if (max_input > 0 and input_ok) or (max_output > 0 and output_ok):
                    supported.append(candidate)
                format_checks.append(
                    {
                        "device_key": f"masked:{private_identifier_digest(private_key)}",
                        "format": candidate.public_dict(),
                        "input_supported": input_ok,
                        "output_supported": output_ok,
                    }
                )
            devices.append(
                AudioDeviceDescriptor(
                    opaque_device_id=private_key,
                    public_name=public_name,
                    platform=_platform_value(),
                    host_api=host_apis.get(host_index, f"host-api-{host_index}"),
                    can_input=max_input > 0,
                    can_output=max_output > 0,
                    default_input=index == default_input,
                    default_output=index == default_output,
                    supported_formats=tuple(supported),
                    reported_input_latency_ms=(
                        (_safe_float(info.get("defaultLowInputLatency")) or 0.0) * 1000
                        if max_input > 0
                        else None
                    ),
                    reported_output_latency_ms=(
                        (_safe_float(info.get("defaultLowOutputLatency")) or 0.0) * 1000
                        if max_output > 0
                        else None
                    ),
                )
            )
        return {
            "host_apis": [host_apis[key] for key in sorted(host_apis)],
            "device_count": len(devices),
            "input_count": sum(item.can_input for item in devices),
            "output_count": sum(item.can_output for item in devices),
            "duplex_count": sum(item.can_input and item.can_output for item in devices),
            "default_input_present": any(item.default_input for item in devices),
            "default_output_present": any(item.default_output for item in devices),
            "devices": [public_device_dict(item) for item in devices],
            "format_checks": format_checks,
            "runtime_sample": process_runtime_sample(),
            "payload_persisted": False,
        }
    finally:
        audio.terminate()


@dataclass(slots=True)
class _LevelAccumulator:
    frame_count: int = 0
    clipped_frames: int = 0
    peaks: list[int] = field(default_factory=list)
    rms_values: list[float] = field(default_factory=list)
    first_frame_ns: int | None = None
    last_frame_ns: int | None = None

    def accept(self, pcm16_le: bytes, timestamp_ns: int) -> None:
        samples = [item[0] for item in struct.iter_unpack("<h", pcm16_le)]
        if not samples:
            return
        peak = max(abs(item) for item in samples)
        rms = math.sqrt(sum(item * item for item in samples) / len(samples))
        self.frame_count += 1
        self.clipped_frames += int(peak >= 32760)
        self.peaks.append(peak)
        self.rms_values.append(rms)
        if len(self.peaks) > 512:
            del self.peaks[: len(self.peaks) - 512]
            del self.rms_values[: len(self.rms_values) - 512]
        self.first_frame_ns = self.first_frame_ns or timestamp_ns
        self.last_frame_ns = timestamp_ns

    def public_dict(self) -> dict[str, object]:
        return {
            "frame_count": self.frame_count,
            "clipped_frames": self.clipped_frames,
            "peak_max": max(self.peaks, default=0),
            "peak_median": (round(statistics.median(self.peaks), 3) if self.peaks else 0.0),
            "rms_median": (
                round(statistics.median(self.rms_values), 3) if self.rms_values else 0.0
            ),
            "first_frame_ns_present": self.first_frame_ns is not None,
            "duration_ms": (
                round((self.last_frame_ns - self.first_frame_ns) / 1_000_000, 3)
                if self.first_frame_ns is not None and self.last_frame_ns is not None
                else 0.0
            ),
        }


def _tone_frame(
    audio_format: PublicAudioFormat, sequence: int, frequency_hz: float = 440.0
) -> bytes:
    amplitude = 1200
    samples = []
    start = sequence * audio_format.samples_per_frame
    for offset in range(audio_format.samples_per_frame):
        value = int(
            amplitude
            * math.sin(
                2.0 * math.pi * frequency_hz * (start + offset) / audio_format.sample_rate_hz
            )
        )
        for _ in range(audio_format.channels):
            samples.append(value)
    return struct.pack("<" + "h" * len(samples), *samples)


def run_pyaudio_duplex_probe(
    *,
    duration_seconds: float = 2.0,
    input_device_index: int | None = None,
    output_device_index: int | None = None,
    sample_rate_hz: int = 16_000,
    channels: int = 1,
    frame_duration_ms: int = 20,
) -> dict[str, object]:
    if not 0.2 <= float(duration_seconds) <= 15.0:
        raise ValueError("duration_seconds must be between 0.2 and 15")
    audio_format = PublicAudioFormat(sample_rate_hz, channels, 2, frame_duration_ms)
    pyaudio = _load_pyaudio()
    audio = pyaudio.PyAudio()
    tracker = ProbeResourceTracker()
    render_timestamps: BoundedProbeQueue[int] = BoundedProbeQueue(256)
    capture_timestamps: BoundedProbeQueue[int] = BoundedProbeQueue(256)
    stop_event = threading.Event()
    capture_levels = _LevelAccumulator()
    errors: list[str] = []
    input_stream: Any | None = None
    output_stream: Any | None = None
    threads: list[threading.Thread] = []
    reported_input_latency_ms: float | None = None
    reported_output_latency_ms: float | None = None
    started_ns = time.perf_counter_ns()

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

        def capture_main() -> None:
            name = threading.current_thread().name
            tracker.add_thread(name)
            try:
                while not stop_event.is_set():
                    raw = input_stream.read(
                        audio_format.samples_per_frame,
                        exception_on_overflow=False,
                    )
                    stamp = time.perf_counter_ns()
                    capture_levels.accept(bytes(raw), stamp)
                    try:
                        capture_timestamps.put(stamp)
                    except ProbeQueueOverflow:
                        errors.append("capture_timestamp_overflow")
                        stop_event.set()
            except Exception as exc:  # native probe boundary
                errors.append(f"capture_failed:{type(exc).__name__}")
                stop_event.set()
            finally:
                tracker.remove_thread(name)

        def render_main() -> None:
            name = threading.current_thread().name
            tracker.add_thread(name)
            sequence = 0
            try:
                while not stop_event.is_set():
                    output_stream.write(_tone_frame(audio_format, sequence))
                    sequence += 1
                    try:
                        render_timestamps.put(time.perf_counter_ns())
                    except ProbeQueueOverflow:
                        errors.append("render_timestamp_overflow")
                        stop_event.set()
            except Exception as exc:  # native probe boundary
                errors.append(f"render_failed:{type(exc).__name__}")
                stop_event.set()
            finally:
                tracker.remove_thread(name)

        reported_input_latency_ms = round(float(input_stream.get_input_latency()) * 1000, 3)
        reported_output_latency_ms = round(float(output_stream.get_output_latency()) * 1000, 3)
        input_stream.start_stream()
        output_stream.start_stream()
        threads = [
            threading.Thread(target=capture_main, name="gate6-probe-capture", daemon=False),
            threading.Thread(target=render_main, name="gate6-probe-render", daemon=False),
        ]
        for thread in threads:
            thread.start()
        stop_event.wait(float(duration_seconds))
    except Exception as exc:
        errors.append(f"duplex_open_failed:{type(exc).__name__}")
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
            if stream is None:
                continue
            try:
                if stream.is_active():
                    stream.stop_stream()
                stream.close()
            except Exception as exc:
                errors.append(f"stream_close_failed:{type(exc).__name__}")
            finally:
                if getattr(tracker, counter) > 0:
                    tracker.decrement(counter)
        if tracker.duplex_sessions:
            tracker.decrement("duplex_sessions")
        audio.terminate()

    render_values = render_timestamps.drain()
    capture_values = capture_timestamps.drain()
    render_timestamps.close()
    capture_timestamps.close()
    terminal = tracker.terminal_dict(
        render_queue=render_timestamps,
        capture_queue=capture_timestamps,
    )
    elapsed_ms = round((time.perf_counter_ns() - started_ns) / 1_000_000, 3)
    return {
        "status": (
            "probe_complete"
            if not errors
            and tracker.is_terminal_zero(
                render_queue=render_timestamps, capture_queue=capture_timestamps
            )
            else "probe_failed"
        ),
        "input_public_name": (
            str(input_info.get("name", "input"))[:120] if "input_info" in locals() else None
        ),
        "output_public_name": (
            str(output_info.get("name", "output"))[:120] if "output_info" in locals() else None
        ),
        "input_device_key": (
            f"masked:{private_identifier_digest(str(input_device_index))}"
            if input_device_index is not None
            else None
        ),
        "output_device_key": (
            f"masked:{private_identifier_digest(str(output_device_index))}"
            if output_device_index is not None
            else None
        ),
        "audio_format": audio_format.public_dict(),
        "duration_ms": elapsed_ms,
        "render_frames": len(render_values),
        "capture_frames": capture_levels.frame_count,
        "render_timestamp_ordered": list(render_values) == sorted(render_values),
        "capture_timestamp_ordered": list(capture_values) == sorted(capture_values),
        "render_queue_peak": render_timestamps.peak,
        "capture_queue_peak": capture_timestamps.peak,
        "render_queue_overflow": render_timestamps.overflow_count,
        "capture_queue_overflow": capture_timestamps.overflow_count,
        "capture_level_summary": capture_levels.public_dict(),
        "reported_input_latency_ms": reported_input_latency_ms,
        "reported_output_latency_ms": reported_output_latency_ms,
        "errors": errors,
        "runtime_sample": process_runtime_sample(),
        "terminal": terminal,
        "pcm_persisted": False,
        "product_uplink_frames": 0,
    }
