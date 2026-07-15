"""Side-effect descriptions emitted by the pure Assistant Runtime reducer."""

from __future__ import annotations

from dataclasses import dataclass

from .state import AssistantEntrySource, AssistantRuntimeMode, VoiceInteractionMode


@dataclass(frozen=True, slots=True)
class AssistantEffect:
    pass


@dataclass(frozen=True, slots=True)
class OpenTransport(AssistantEffect):
    generation: int
    runtime_mode: AssistantRuntimeMode


@dataclass(frozen=True, slots=True)
class CloseTransport(AssistantEffect):
    generation: int
    reason: str


@dataclass(frozen=True, slots=True)
class SendText(AssistantEffect):
    generation: int
    turn_token: int
    text: str


@dataclass(frozen=True, slots=True)
class CancelRuntimeEffects(AssistantEffect):
    reason: str


@dataclass(frozen=True, slots=True)
class EnsureIdentity(AssistantEffect):
    pass


@dataclass(frozen=True, slots=True)
class ResetIdentity(AssistantEffect):
    pass


@dataclass(frozen=True, slots=True)
class RunActivation(AssistantEffect):
    fake: bool


@dataclass(frozen=True, slots=True)
class ScheduleReconnect(AssistantEffect):
    attempt: int
    delay_seconds: float
    generation: int


@dataclass(frozen=True, slots=True)
class CancelReconnect(AssistantEffect):
    pass


@dataclass(frozen=True, slots=True)
class SetVoiceInteractionMode(AssistantEffect):
    mode: VoiceInteractionMode


@dataclass(frozen=True, slots=True)
class SetStreamingBargeIn(AssistantEffect):
    enabled: bool


@dataclass(frozen=True, slots=True)
class StartPushToTalk(AssistantEffect):
    generation: int


@dataclass(frozen=True, slots=True)
class StopPushToTalk(AssistantEffect):
    generation: int


@dataclass(frozen=True, slots=True)
class StartStreamingConversation(AssistantEffect):
    generation: int
    source: AssistantEntrySource
    wake_keyword: str | None


@dataclass(frozen=True, slots=True)
class StopStreamingConversation(AssistantEffect):
    generation: int
    reason: str


@dataclass(frozen=True, slots=True)
class AbortCurrentTurn(AssistantEffect):
    reason: str


@dataclass(frozen=True, slots=True)
class HandleSystemAudioInterruption(AssistantEffect):
    reason: str
    resume_wakeword: bool


@dataclass(frozen=True, slots=True)
class HandleSystemAudioRecovered(AssistantEffect):
    reason: str


@dataclass(frozen=True, slots=True)
class StartPlayback(AssistantEffect):
    generation: int


@dataclass(frozen=True, slots=True)
class StopPlayback(AssistantEffect):
    generation: int
    reason: str


@dataclass(frozen=True, slots=True)
class ExecuteMcpRequest(AssistantEffect):
    request_id: str
    payload_json: str


@dataclass(frozen=True, slots=True)
class StartWakeWord(AssistantEffect):
    generation: int


@dataclass(frozen=True, slots=True)
class StopWakeWord(AssistantEffect):
    generation: int
    reason: str


@dataclass(frozen=True, slots=True)
class RecordMetric(AssistantEffect):
    name: str
    at_ns: int
    fields: tuple[tuple[str, str], ...] = ()
