"""Immutable playback hot-path models for Gate 4.1."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..protocol.events import DownlinkAudioFormat


class PlaybackLifecycleState(str, Enum):
    ARMED = "armed"
    BUFFERING = "buffering"
    PLAYING = "playing"
    DRAINED = "drained"
    CANCELLED = "cancelled"
    FAILED = "failed"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class PcmAudioFormat:
    sample_rate_hz: int
    channels: int
    sample_width_bytes: int = 2

    def __post_init__(self) -> None:
        if self.sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive")
        if self.channels <= 0:
            raise ValueError("channels must be positive")
        if self.sample_width_bytes not in {1, 2, 3, 4}:
            raise ValueError("unsupported sample_width_bytes")

    @property
    def frame_size_bytes(self) -> int:
        return self.channels * self.sample_width_bytes


@dataclass(frozen=True, slots=True)
class TtsStreamContext:
    connection_generation: int
    stream_sequence: int
    playback_generation: int
    turn_token: int
    streaming_generation: int | None
    wire_format: DownlinkAudioFormat
    started_at_ns: int
    session_id: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "connection_generation",
            "stream_sequence",
            "playback_generation",
            "turn_token",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.streaming_generation is not None and self.streaming_generation <= 0:
            raise ValueError("streaming_generation must be positive when present")
        if self.started_at_ns < 0:
            raise ValueError("started_at_ns must be non-negative")


@dataclass(frozen=True, slots=True)
class EncodedDownlinkPacket:
    connection_generation: int
    stream_sequence: int
    packet_sequence: int
    received_at_ns: int
    payload: bytes

    def __post_init__(self) -> None:
        if self.connection_generation <= 0:
            raise ValueError("connection_generation must be positive")
        if self.stream_sequence <= 0:
            raise ValueError("stream_sequence must be positive")
        if self.packet_sequence <= 0:
            raise ValueError("packet_sequence must be positive")
        if self.received_at_ns < 0:
            raise ValueError("received_at_ns must be non-negative")
        if not isinstance(self.payload, bytes) or not self.payload:
            raise ValueError("payload must be non-empty bytes")


@dataclass(frozen=True, slots=True)
class DecodedPcmChunk:
    pcm_format: PcmAudioFormat
    payload: bytes
    decoded_at_ns: int

    def __post_init__(self) -> None:
        if self.decoded_at_ns < 0:
            raise ValueError("decoded_at_ns must be non-negative")
        if not isinstance(self.payload, bytes) or not self.payload:
            raise ValueError("payload must be non-empty bytes")
        if len(self.payload) % self.pcm_format.frame_size_bytes:
            raise ValueError("PCM payload is not frame aligned")

    @property
    def sample_frames(self) -> int:
        return len(self.payload) // self.pcm_format.frame_size_bytes


@dataclass(slots=True)
class PlaybackMetrics:
    encoded_packets_received: int = 0
    encoded_bytes_received: int = 0
    decoded_chunks: int = 0
    decoded_sample_frames: int = 0
    played_sample_frames: int = 0
    encoded_overflow_count: int = 0
    pcm_overflow_count: int = 0
    pcm_underflow_count: int = 0
    stale_packet_count: int = 0
    buffer_peak_bytes: int = 0
    first_packet_at_ns: int | None = None
    first_decoded_at_ns: int | None = None
    playback_started_at_ns: int | None = None
    input_terminal_at_ns: int | None = None
    playback_ended_at_ns: int | None = None


@dataclass(frozen=True, slots=True)
class PlaybackSummary:
    connection_generation: int
    stream_sequence: int
    playback_generation: int
    turn_token: int
    streaming_generation: int | None
    reason: str
    natural_end: bool
    encoded_packets_received: int
    encoded_bytes_received: int
    decoded_chunks: int
    decoded_sample_frames: int
    played_sample_frames: int
    encoded_overflow_count: int
    pcm_overflow_count: int
    pcm_underflow_count: int
    buffer_peak_bytes: int
    output_device_public_name: str | None


@dataclass(frozen=True, slots=True)
class PlaybackStartedSignal:
    connection_generation: int
    stream_sequence: int
    playback_generation: int
    turn_token: int
    streaming_generation: int | None
    at_ns: int


@dataclass(frozen=True, slots=True)
class PlaybackEndedSignal:
    summary: PlaybackSummary


@dataclass(frozen=True, slots=True)
class PlaybackCancelledSignal:
    connection_generation: int
    stream_sequence: int
    playback_generation: int
    turn_token: int
    reason: str
    at_ns: int


@dataclass(frozen=True, slots=True)
class PlaybackFailedSignal:
    connection_generation: int
    stream_sequence: int
    playback_generation: int
    turn_token: int
    code: str
    message: str
    at_ns: int


PlaybackSignal = (
    PlaybackStartedSignal | PlaybackEndedSignal | PlaybackCancelledSignal | PlaybackFailedSignal
)
