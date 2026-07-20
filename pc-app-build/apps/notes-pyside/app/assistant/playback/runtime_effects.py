"""Gate 4.2 playback effects executed outside the single state writer."""

from __future__ import annotations

from dataclasses import dataclass

from ..effects import AssistantEffect


@dataclass(frozen=True, slots=True)
class StartActualPlayback(AssistantEffect):
    connection_generation: int
    stream_sequence: int
    playback_generation: int
    turn_token: int


@dataclass(frozen=True, slots=True)
class CancelActualPlayback(AssistantEffect):
    playback_generation: int
    reason: str


@dataclass(frozen=True, slots=True)
class AbortPlaybackTurn(AssistantEffect):
    connection_generation: int
    playback_generation: int
    turn_token: int
    capture_generation: int
    reason: str
