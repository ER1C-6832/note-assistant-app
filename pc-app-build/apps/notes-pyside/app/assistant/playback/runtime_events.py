"""Small immutable Runtime events for Gate 4.2 playback control."""

from __future__ import annotations

from dataclasses import dataclass

from ..events import AssistantEvent
from ..protocol.events import DownlinkAudioFormat
from .models import PlaybackSummary


@dataclass(frozen=True, slots=True, kw_only=True)
class TtsPlaybackStreamStarted(AssistantEvent):
    connection_generation: int
    stream_sequence: int
    playback_generation: int
    turn_token: int
    wire_format: DownlinkAudioFormat
    streaming_generation: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class TtsPlaybackInputEnded(AssistantEvent):
    connection_generation: int
    stream_sequence: int
    playback_generation: int
    turn_token: int
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ActualPlaybackStarted(AssistantEvent):
    connection_generation: int
    stream_sequence: int
    playback_generation: int
    turn_token: int
    streaming_generation: int | None = None
    output_device_public_name: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class PlaybackProgressUpdated(AssistantEvent):
    connection_generation: int
    stream_sequence: int
    playback_generation: int
    turn_token: int
    decoded_sample_frames: int
    played_sample_frames: int
    encoded_packets_received: int
    pcm_underflow_count: int
    encoded_overflow_count: int
    pcm_overflow_count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ActualPlaybackEnded(AssistantEvent):
    summary: PlaybackSummary


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimePlaybackCancelled(AssistantEvent):
    connection_generation: int
    stream_sequence: int
    playback_generation: int
    turn_token: int
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimePlaybackFailed(AssistantEvent):
    connection_generation: int
    stream_sequence: int
    playback_generation: int
    turn_token: int
    code: str
    message: str
