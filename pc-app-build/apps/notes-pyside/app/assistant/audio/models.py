"""Immutable audio contracts shared by PTT and streaming conversation."""

from __future__ import annotations

from dataclasses import dataclass

from ..state import VoiceActivityState

DEFAULT_SAMPLE_RATE_HZ = 16_000
DEFAULT_CHANNELS = 1
DEFAULT_FRAME_DURATION_MS = 20
DEFAULT_SAMPLES_PER_FRAME = 320
DEFAULT_BYTES_PER_FRAME = 640
DEFAULT_OPUS_BITRATE_BPS = 24_000


@dataclass(frozen=True, slots=True)
class PcmFrame:
    generation: int
    sequence: int
    captured_at_ns: int
    pcm16_le: bytes

    def validate(self) -> None:
        if self.generation < 0 or self.sequence < 0 or self.captured_at_ns < 0:
            raise ValueError("PCM frame counters cannot be negative")
        if not isinstance(self.pcm16_le, bytes):
            raise TypeError("pcm16_le must be bytes")


@dataclass(frozen=True, slots=True)
class EncodedAudioPacket:
    generation: int
    sequence: int
    encoded_at_ns: int
    payload: bytes

    def validate(self) -> None:
        if self.generation < 0 or self.sequence < 0 or self.encoded_at_ns < 0:
            raise ValueError("encoded packet counters cannot be negative")
        if not self.payload:
            raise ValueError("encoded packet payload cannot be empty")


@dataclass(frozen=True, slots=True)
class VoiceActivitySnapshot:
    generation: int
    frame_sequence: int
    state: VoiceActivityState
    peak_abs: int = 0
    rms: float = 0.0
    elapsed_ms: int = 0


@dataclass(frozen=True, slots=True)
class AudioCaptureSummary:
    generation: int
    captured_frames: int
    encoded_frames: int
    dropped_pcm_frames: int
    speech_seen: bool
    stopped_within_budget: bool
    stop_latency_ms: int
    error_message: str | None = None
