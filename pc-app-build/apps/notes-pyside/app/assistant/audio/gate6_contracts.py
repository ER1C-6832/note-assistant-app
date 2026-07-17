"""Framework-neutral Gate 6 audio/device contracts.

Gate 6.0 freezes these value objects and ports before any production audio
routing changes.  The module intentionally imports no Qt, PyAudio, platform
API, model runtime, or application state type.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, TypeAlias, runtime_checkable


class AudioPlatform(str, Enum):
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"
    OTHER = "other"


class DeviceDirection(str, Enum):
    INPUT = "input"
    OUTPUT = "output"


class DevicePreferenceMode(str, Enum):
    FOLLOW_SYSTEM_DEFAULT = "follow_system_default"
    PIN_SPECIFIC_DEVICE = "pin_specific_device"


class CaptureActivity(str, Enum):
    INACTIVE = "inactive"
    WAKEWORD_KWS = "kws"
    ASSISTANT = "assistant"
    BARGE_IN_MONITOR = "barge_in_monitor"


class PlaybackActivity(str, Enum):
    INACTIVE = "inactive"
    BUFFERING = "buffering"
    PLAYING = "playing"
    DRAINING = "draining"
    CANCELLING = "cancelling"


class ProcessingState(str, Enum):
    BYPASS = "bypass"
    WARMING = "warming"
    READY = "ready"
    DEGRADED = "degraded"
    FAILED = "failed"


class AudioRouteState(str, Enum):
    UNAVAILABLE = "unavailable"
    RESOLVING = "resolving"
    READY = "ready"
    INTERRUPTED = "interrupted"


class MicrophoneOwner(str, Enum):
    NONE = "none"
    WAKEWORD_KWS = "wakeword_kws"
    ASSISTANT_CAPTURE = "assistant_capture"
    BARGE_IN_MONITOR = "barge_in_monitor"


class RouteEventKind(str, Enum):
    SNAPSHOT_CHANGED = "snapshot_changed"
    DEFAULT_CHANGED = "default_changed"
    DEVICE_ADDED = "device_added"
    DEVICE_REMOVED = "device_removed"
    DEVICE_DEAD = "device_dead"
    FORMAT_CHANGED = "format_changed"
    PERMISSION_CHANGED = "permission_changed"
    AUDIO_SERVICE_RESTARTED = "audio_service_restarted"
    INTERRUPTED = "interrupted"
    RECOVERED = "recovered"


@dataclass(frozen=True, slots=True)
class PublicAudioFormat:
    sample_rate_hz: int
    channels: int
    sample_width_bytes: int = 2
    frame_duration_ms: int = 20

    def __post_init__(self) -> None:
        if self.sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive")
        if self.channels <= 0:
            raise ValueError("channels must be positive")
        if self.sample_width_bytes not in {1, 2, 3, 4}:
            raise ValueError("unsupported sample width")
        if self.frame_duration_ms not in {5, 10, 20, 30, 40, 60}:
            raise ValueError("unsupported frame duration")
        samples = self.sample_rate_hz * self.frame_duration_ms
        if samples % 1000:
            raise ValueError("frame duration does not map to an integer sample count")

    @property
    def samples_per_frame(self) -> int:
        return self.sample_rate_hz * self.frame_duration_ms // 1000

    @property
    def bytes_per_frame(self) -> int:
        return self.samples_per_frame * self.channels * self.sample_width_bytes

    def public_dict(self) -> dict[str, int]:
        return {
            "sample_rate_hz": self.sample_rate_hz,
            "channels": self.channels,
            "sample_width_bytes": self.sample_width_bytes,
            "frame_duration_ms": self.frame_duration_ms,
        }


@dataclass(frozen=True, slots=True)
class AudioDeviceDescriptor:
    opaque_device_id: str = field(repr=False)
    public_name: str
    platform: AudioPlatform
    host_api: str
    can_input: bool
    can_output: bool
    default_input: bool = False
    default_output: bool = False
    supported_formats: tuple[PublicAudioFormat, ...] = ()
    available: bool = True
    route_class: str | None = None
    reported_input_latency_ms: float | None = None
    reported_output_latency_ms: float | None = None

    def __post_init__(self) -> None:
        if not self.opaque_device_id.strip():
            raise ValueError("opaque_device_id cannot be empty")
        if not self.public_name.strip():
            raise ValueError("public_name cannot be empty")
        if not (self.can_input or self.can_output):
            raise ValueError("device must support input or output")
        if self.default_input and not self.can_input:
            raise ValueError("default_input requires input capability")
        if self.default_output and not self.can_output:
            raise ValueError("default_output requires output capability")


@dataclass(frozen=True, slots=True)
class AudioDeviceSnapshot:
    generation: int
    devices: tuple[AudioDeviceDescriptor, ...]
    captured_at_ns: int
    error_code: str | None = None

    def __post_init__(self) -> None:
        if self.generation < 0:
            raise ValueError("generation cannot be negative")
        if self.captured_at_ns < 0:
            raise ValueError("captured_at_ns cannot be negative")
        ids = [item.opaque_device_id for item in self.devices]
        if len(ids) != len(set(ids)):
            raise ValueError("device snapshot contains duplicate opaque ids")


@dataclass(frozen=True, slots=True)
class DevicePreference:
    direction: DeviceDirection
    mode: DevicePreferenceMode = DevicePreferenceMode.FOLLOW_SYSTEM_DEFAULT
    pinned_device_id: str | None = field(default=None, repr=False)
    allow_temporary_default_fallback: bool = True

    def __post_init__(self) -> None:
        pinned = (self.pinned_device_id or "").strip()
        if self.mode is DevicePreferenceMode.PIN_SPECIFIC_DEVICE and not pinned:
            raise ValueError("pinned mode requires a private device id")
        if self.mode is DevicePreferenceMode.FOLLOW_SYSTEM_DEFAULT and pinned:
            raise ValueError("default-following mode cannot carry a pinned device id")


@dataclass(frozen=True, slots=True)
class ResolvedAudioRoute:
    route_generation: int
    input_device: AudioDeviceDescriptor | None
    output_device: AudioDeviceDescriptor | None
    input_preference: DevicePreference
    output_preference: DevicePreference
    state: AudioRouteState
    temporary_input_fallback: bool = False
    temporary_output_fallback: bool = False
    error_code: str | None = None

    def __post_init__(self) -> None:
        if self.route_generation < 0:
            raise ValueError("route_generation cannot be negative")
        if self.input_device is not None and not self.input_device.can_input:
            raise ValueError("resolved input does not support input")
        if self.output_device is not None and not self.output_device.can_output:
            raise ValueError("resolved output does not support output")
        if self.state is AudioRouteState.READY and (
            self.input_device is None or self.output_device is None
        ):
            raise ValueError("ready duplex route requires input and output")


@dataclass(frozen=True, slots=True)
class TimedPcmFrame:
    route_generation: int
    stream_generation: int
    sequence: int
    monotonic_ns: int
    audio_format: PublicAudioFormat
    pcm16_le: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if (
            min(
                self.route_generation,
                self.stream_generation,
                self.sequence,
                self.monotonic_ns,
            )
            < 0
        ):
            raise ValueError("frame generations, sequence and timestamp cannot be negative")
        if len(self.pcm16_le) != self.audio_format.bytes_per_frame:
            raise ValueError("PCM frame size does not match its declared format")


@dataclass(frozen=True, slots=True)
class ProcessedPcmFrame:
    source: TimedPcmFrame = field(repr=False)
    pcm16_le: bytes = field(repr=False)
    processing_state: ProcessingState = ProcessingState.BYPASS
    backend_public_name: str = "bypass"
    speech_probability: float | None = None

    def __post_init__(self) -> None:
        if len(self.pcm16_le) != self.source.audio_format.bytes_per_frame:
            raise ValueError("processed frame size does not match source format")
        if self.speech_probability is not None and not 0.0 <= self.speech_probability <= 1.0:
            raise ValueError("speech_probability must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class AudioProcessingMetrics:
    backend_public_name: str
    state: ProcessingState
    aec_available: bool
    aec_effective: bool
    ns_available: bool
    ns_effective: bool
    agc_available: bool
    agc_effective: bool = False
    render_frames: int = 0
    capture_frames: int = 0
    processed_frames: int = 0
    render_queue_peak: int = 0
    capture_queue_peak: int = 0
    overflow_count: int = 0
    estimated_delay_ms: float | None = None
    estimated_drift_ppm: float | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        counters = (
            self.render_frames,
            self.capture_frames,
            self.processed_frames,
            self.render_queue_peak,
            self.capture_queue_peak,
            self.overflow_count,
        )
        if any(value < 0 for value in counters):
            raise ValueError("processing counters cannot be negative")
        if self.agc_effective and not self.agc_available:
            raise ValueError("AGC cannot be effective when unavailable")


@dataclass(frozen=True, slots=True)
class KeywordSpotResult:
    generation: int
    keyword_public_name: str
    detected_at_ns: int
    score: float | None = None

    def __post_init__(self) -> None:
        if self.generation < 0 or self.detected_at_ns < 0:
            raise ValueError("keyword generations/timestamps cannot be negative")
        if not self.keyword_public_name.strip():
            raise ValueError("keyword name cannot be empty")


@dataclass(frozen=True, slots=True)
class DuplexAudioPlan:
    route_generation: int
    capture_format: PublicAudioFormat
    render_format: PublicAudioFormat
    internal_block_ms: int
    render_queue_capacity: int
    capture_queue_capacity: int
    watchdog_ms: int

    def __post_init__(self) -> None:
        if self.route_generation < 0:
            raise ValueError("route_generation cannot be negative")
        if self.internal_block_ms not in {5, 10, 20}:
            raise ValueError("internal block must be 5, 10 or 20 ms")
        if (
            min(
                self.render_queue_capacity,
                self.capture_queue_capacity,
                self.watchdog_ms,
            )
            <= 0
        ):
            raise ValueError("queue capacities and watchdog must be positive")


CaptureFrameSink: TypeAlias = Callable[[TimedPcmFrame], None]
RenderFrameSource: TypeAlias = Callable[[], TimedPcmFrame | None]
RouteEventSink: TypeAlias = Callable[["AudioRouteEvent"], None]


@dataclass(frozen=True, slots=True)
class DuplexCallbacks:
    capture_sink: CaptureFrameSink
    render_source: RenderFrameSource


@dataclass(frozen=True, slots=True)
class AudioRouteEvent:
    generation: int
    kind: RouteEventKind
    monotonic_ns: int
    public_summary: str
    error_code: str | None = None

    def __post_init__(self) -> None:
        if self.generation < 0 or self.monotonic_ns < 0:
            raise ValueError("route event generation/timestamp cannot be negative")


@runtime_checkable
class AudioDeviceRegistryPort(Protocol):
    def snapshot(self) -> AudioDeviceSnapshot: ...

    def resolve(
        self,
        input_preference: DevicePreference,
        output_preference: DevicePreference,
    ) -> ResolvedAudioRoute: ...


@runtime_checkable
class AudioRouteObserverPort(Protocol):
    def start(self, sink: RouteEventSink) -> None: ...

    def stop(self) -> None: ...

    def close(self) -> None: ...


@runtime_checkable
class DuplexAudioSessionPort(Protocol):
    def open(self, plan: DuplexAudioPlan, callbacks: DuplexCallbacks) -> None: ...

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def close(self) -> None: ...


@runtime_checkable
class AudioProcessingPort(Protocol):
    def process_render(self, frame: TimedPcmFrame) -> None: ...

    def process_capture(self, frame: TimedPcmFrame) -> ProcessedPcmFrame: ...

    def metrics(self) -> AudioProcessingMetrics: ...

    def close(self) -> None: ...


@runtime_checkable
class KeywordSpotterPort(Protocol):
    def accept(self, frame: ProcessedPcmFrame) -> KeywordSpotResult | None: ...

    def reset(self, generation: int) -> None: ...

    def close(self) -> None: ...


def public_format_set(
    values: Sequence[PublicAudioFormat],
) -> tuple[PublicAudioFormat, ...]:
    """Return a stable unique format tuple without exposing native handles."""

    unique: dict[tuple[int, int, int, int], PublicAudioFormat] = {}
    for value in values:
        key = (
            value.sample_rate_hz,
            value.channels,
            value.sample_width_bytes,
            value.frame_duration_ms,
        )
        unique[key] = value
    return tuple(unique[key] for key in sorted(unique))


def state_projection(
    *,
    capture: CaptureActivity,
    playback: PlaybackActivity,
    processing: ProcessingState,
    route: AudioRouteState,
) -> Mapping[str, str]:
    """Produce a coarse public projection; never carries PCM or native objects."""

    return {
        "capture_activity": capture.value,
        "playback_activity": playback.value,
        "processing_state": processing.value,
        "route_state": route.value,
    }
