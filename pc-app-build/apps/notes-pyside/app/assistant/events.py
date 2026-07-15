"""Typed events accepted by the single Assistant Runtime event pump."""

from __future__ import annotations

from dataclasses import dataclass

from .state import (
    AssistantEntrySource,
    MicrophoneOwner,
    StreamingConversationState,
    VoiceActivityState,
    VoiceInteractionMode,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class AssistantEvent:
    at_ns: int


@dataclass(frozen=True, slots=True, kw_only=True)
class EnableRequested(AssistantEvent):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class DisableRequested(AssistantEvent):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class UseFakeRuntimeRequested(AssistantEvent):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class UseRealRuntimeRequested(AssistantEvent):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class ConnectRequested(AssistantEvent):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class ReconnectRequested(AssistantEvent):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class DisconnectRequested(AssistantEvent):
    reason: str = "user_disconnect"


@dataclass(frozen=True, slots=True, kw_only=True)
class TextSubmitted(AssistantEvent):
    text: str


@dataclass(frozen=True, slots=True, kw_only=True)
class VoiceInteractionModeRequested(AssistantEvent):
    mode: VoiceInteractionMode


@dataclass(frozen=True, slots=True, kw_only=True)
class StreamingBargeInRequested(AssistantEvent):
    enabled: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class PushToTalkStartRequested(AssistantEvent):
    permission_granted: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class PushToTalkStopRequested(AssistantEvent):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class StreamingConversationStartRequested(AssistantEvent):
    permission_granted: bool
    source: AssistantEntrySource = AssistantEntrySource.STREAMING_BUTTON
    wake_keyword: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class StreamingConversationStopRequested(AssistantEvent):
    reason: str = "user_stop"


@dataclass(frozen=True, slots=True, kw_only=True)
class AbortRequested(AssistantEvent):
    reason: str = "user_interruption"


@dataclass(frozen=True, slots=True, kw_only=True)
class SystemAudioInterrupted(AssistantEvent):
    reason: str
    resume_wakeword: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class SystemAudioRecovered(AssistantEvent):
    reason: str = "system_audio_recovered"


@dataclass(frozen=True, slots=True, kw_only=True)
class EnsureIdentityRequested(AssistantEvent):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class ResetIdentityRequested(AssistantEvent):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class FakeActivationRequested(AssistantEvent):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class RealActivationRequested(AssistantEvent):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class IncomingToolCallSimulationRequested(AssistantEvent):
    tool_name: str
    arguments_json: str = "{}"


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolsListSimulationRequested(AssistantEvent):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class ConnectionClosedSimulationRequested(AssistantEvent):
    code: int = 1006
    reason: str = "debug_abnormal_close"


@dataclass(frozen=True, slots=True, kw_only=True)
class ConnectionFailureSimulationRequested(AssistantEvent):
    message: str = "debug_transport_failure"


@dataclass(frozen=True, slots=True, kw_only=True)
class AudioFailureSimulationRequested(AssistantEvent):
    message: str = "debug_audio_failure"


@dataclass(frozen=True, slots=True, kw_only=True)
class ShutdownRequested(AssistantEvent):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class TransportOpened(AssistantEvent):
    generation: int
    websocket_url_public: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ClientHelloSent(AssistantEvent):
    generation: int
    raw_json_redacted: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ServerHelloReceived(AssistantEvent):
    generation: int
    session_id: str
    transport: str | None = None
    raw_json_redacted: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class AssistantTextReceived(AssistantEvent):
    generation: int
    text: str
    source_type: str = "text"
    session_id: str | None = None
    raw_json_redacted: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ProtocolMessageObserved(AssistantEvent):
    generation: int
    event_name: str
    message_type: str
    session_id: str | None = None
    raw_json_redacted: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ProtocolUnknownMessageReceived(AssistantEvent):
    generation: int
    message_type: str
    session_id: str | None = None
    raw_json_redacted: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ProtocolInvalidMessageReceived(AssistantEvent):
    generation: int
    error: str
    raw_text_redacted: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BinaryAudioReceived(AssistantEvent):
    generation: int
    size_bytes: int


@dataclass(frozen=True, slots=True, kw_only=True)
class TransportClosed(AssistantEvent):
    generation: int
    code: int
    reason: str
    expected: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class TransportFailed(AssistantEvent):
    generation: int
    message: str


@dataclass(frozen=True, slots=True, kw_only=True)
class EffectExecutionFailed(AssistantEvent):
    effect_name: str
    message: str
    generation: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class IdentityReady(AssistantEvent):
    device_id_masked: str
    client_id_masked: str
    identity_generation: int


@dataclass(frozen=True, slots=True, kw_only=True)
class IdentityReset(AssistantEvent):
    identity_generation: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ActivationStarted(AssistantEvent):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class ActivationRequired(AssistantEvent):
    activation_code: str
    authorization_url: str
    message: str
    websocket_url_public: str | None = None
    diagnostics_json_redacted: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ActivationSucceeded(AssistantEvent):
    websocket_url_public: str
    message: str
    diagnostics_json_redacted: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ActivationFailed(AssistantEvent):
    message: str
    diagnostics_json_redacted: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ReconnectTimerFired(AssistantEvent):
    generation: int
    attempt: int


@dataclass(frozen=True, slots=True, kw_only=True)
class AudioCaptureStarted(AssistantEvent):
    generation: int


@dataclass(frozen=True, slots=True, kw_only=True)
class AudioCaptureStopped(AssistantEvent):
    generation: int
    summary: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class AudioCountersUpdated(AssistantEvent):
    generation: int
    captured_frames: int
    encoded_frames: int
    uploaded_frames: int


@dataclass(frozen=True, slots=True, kw_only=True)
class PlaybackStarted(AssistantEvent):
    generation: int


@dataclass(frozen=True, slots=True, kw_only=True)
class PlaybackEnded(AssistantEvent):
    generation: int


@dataclass(frozen=True, slots=True, kw_only=True)
class PlaybackCountersUpdated(AssistantEvent):
    generation: int
    decoded_frames: int
    played_frames: int


@dataclass(frozen=True, slots=True, kw_only=True)
class VoiceActivityChanged(AssistantEvent):
    generation: int
    state: VoiceActivityState
    status_text: str


@dataclass(frozen=True, slots=True, kw_only=True)
class StreamingSessionStarted(AssistantEvent):
    generation: int
    session_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class StreamingTurnChanged(AssistantEvent):
    generation: int
    turn_index: int
    state: StreamingConversationState


@dataclass(frozen=True, slots=True, kw_only=True)
class StreamingSessionStopped(AssistantEvent):
    generation: int
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BargeInTriggered(AssistantEvent):
    generation: int


@dataclass(frozen=True, slots=True, kw_only=True)
class MicrophoneLeaseChanged(AssistantEvent):
    owner: MicrophoneOwner
    generation: int
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class McpRequestReceived(AssistantEvent):
    request_id: str
    method: str
    tool_name: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class McpRequestCompleted(AssistantEvent):
    request_id: str
    status: str
    tool_name: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class WakeWordDetected(AssistantEvent):
    generation: int
    keyword: str


@dataclass(frozen=True, slots=True, kw_only=True)
class KwsStateChanged(AssistantEvent):
    generation: int
    active: bool
    status_text: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimeOverloaded(AssistantEvent):
    message: str
