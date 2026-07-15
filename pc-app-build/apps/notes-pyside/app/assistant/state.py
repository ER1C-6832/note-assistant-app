"""Immutable Assistant Runtime state shared by every future runtime gate."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class StringEnum(str, Enum):
    """Python 3.10 compatible string enum."""

    def __str__(self) -> str:
        return self.value


class AssistantPhase(StringEnum):
    DISABLED = "disabled"
    IDLE = "idle"
    ACTIVATING = "activating"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    LISTENING = "listening"
    UPLOADING_AUDIO = "uploading_audio"
    THINKING = "thinking"
    SPEAKING = "speaking"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class AssistantRuntimeMode(StringEnum):
    FAKE = "fake"
    REAL = "real"


class AssistantConnectionStatus(StringEnum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CLOSING = "closing"


class AssistantActivationStatus(StringEnum):
    UNKNOWN = "unknown"
    REQUIRED = "required"
    ACTIVATING = "activating"
    ACTIVATED = "activated"
    FAILED = "failed"


class AssistantAudioStatus(StringEnum):
    IDLE = "idle"
    RECORDING = "recording"
    PLAYING = "playing"
    ERROR = "error"


class VoiceInteractionMode(StringEnum):
    HOLD_TO_TALK = "hold_to_talk"
    STREAMING_CONVERSATION = "streaming_conversation"


class AssistantEntrySource(StringEnum):
    TEXT = "text"
    PUSH_TO_TALK = "push_to_talk"
    STREAMING_BUTTON = "streaming_button"
    WAKEWORD = "wakeword"


class StreamingConversationState(StringEnum):
    INACTIVE = "inactive"
    STARTING = "starting"
    LISTENING_FOR_SPEECH = "listening_for_speech"
    USER_SPEAKING = "user_speaking"
    SUBMITTING_TURN = "submitting_turn"
    THINKING = "thinking"
    SPEAKING = "speaking"
    WAITING_FOR_NEXT_TURN = "waiting_for_next_turn"
    STOPPING = "stopping"
    RECOVERING = "recovering"
    ERROR = "error"


class VoiceActivityState(StringEnum):
    DISABLED = "disabled"
    WARMUP = "warmup"
    WAITING_FOR_SPEECH = "waiting_for_speech"
    SPEECH_DETECTED = "speech_detected"
    SPEECH_ACTIVE = "speech_active"
    END_OF_SPEECH = "end_of_speech"
    NO_SPEECH_TIMEOUT = "no_speech_timeout"


class MicrophoneOwner(StringEnum):
    NONE = "none"
    WAKEWORD_KWS = "wakeword_kws"
    ASSISTANT_CAPTURE = "assistant_capture"


class AssistantErrorCategory(StringEnum):
    VALIDATION = "validation"
    CAPABILITY = "capability"
    TRANSPORT = "transport"
    PROTOCOL = "protocol"
    IDENTITY = "identity"
    ACTIVATION = "activation"
    AUDIO = "audio"
    MCP = "mcp"
    RUNTIME = "runtime"


class CapabilityStatus(StringEnum):
    ACTIVE = "active"
    NOT_READY = "not_ready"
    INACTIVE = "inactive"


class AssistantCapability(StringEnum):
    RUNTIME_CORE = "runtime_core"
    FAKE_TRANSPORT = "fake_transport"
    REAL_TRANSPORT = "real_transport"
    IDENTITY = "identity"
    ACTIVATION = "activation"
    TEXT_CONVERSATION = "text_conversation"
    MANUAL_RECOVERY = "manual_recovery"
    AUTOMATIC_RECOVERY = "automatic_recovery"
    ABORT_CURRENT_TURN = "abort_current_turn"
    PUSH_TO_TALK = "push_to_talk"
    TTS_PLAYBACK = "tts_playback"
    MCP_PROTOCOL = "mcp_protocol"
    MCP_NOTES = "mcp_notes"
    STREAMING_CONVERSATION = "streaming_conversation"
    VAD = "vad"
    BARGE_IN = "barge_in"
    MICROPHONE_OWNERSHIP = "microphone_ownership"
    KWS = "kws"
    SYSTEM_AUDIO_RECOVERY = "system_audio_recovery"
    METRICS_BASE = "metrics_base"


@dataclass(frozen=True, slots=True)
class CapabilityState:
    name: AssistantCapability
    status: CapabilityStatus
    target_gate: str
    detail: str


@dataclass(frozen=True, slots=True)
class ConnectionState:
    status: AssistantConnectionStatus = AssistantConnectionStatus.DISCONNECTED
    session_id: str | None = None
    websocket_url_public: str | None = None
    connection_generation: int = 0
    opened_at_ns: int | None = None
    hello_sent_at_ns: int | None = None
    hello_received_at_ns: int | None = None
    close_code: int | None = None
    close_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ActivationState:
    status: AssistantActivationStatus = AssistantActivationStatus.UNKNOWN
    activation_code: str | None = None
    message: str | None = None
    authorization_url: str | None = None
    last_attempt_at_ns: int | None = None


@dataclass(frozen=True, slots=True)
class IdentityPublicState:
    device_id_masked: str | None = None
    client_id_masked: str | None = None
    identity_ready: bool = False
    identity_generation: int = 0


@dataclass(frozen=True, slots=True)
class AudioState:
    status: AssistantAudioStatus = AssistantAudioStatus.IDLE
    capture_generation: int = 0
    playback_generation: int = 0
    wakeword_generation: int = 0
    microphone_lease_generation: int = 0
    captured_frames: int = 0
    encoded_frames: int = 0
    uploaded_frames: int = 0
    decoded_frames: int = 0
    played_frames: int = 0
    last_audio_summary: str | None = None
    push_to_talk_stop_latency_ms: int | None = None
    microphone_owner: MicrophoneOwner = MicrophoneOwner.NONE


@dataclass(frozen=True, slots=True)
class ConversationState:
    preferred_voice_mode: VoiceInteractionMode = VoiceInteractionMode.HOLD_TO_TALK
    active_entry_source: AssistantEntrySource | None = None
    last_user_text: str | None = None
    last_assistant_text: str | None = None
    streaming_state: StreamingConversationState = StreamingConversationState.INACTIVE
    streaming_session_active: bool = False
    streaming_generation: int = 0
    streaming_session_id: str | None = None
    streaming_turn_index: int = 0
    streaming_idle_timeout_ms: int = 15_000
    streaming_barge_in_enabled: bool = False
    barge_in_monitor_active: bool = False
    barge_in_trigger_count: int = 0
    vad_state: VoiceActivityState = VoiceActivityState.DISABLED
    vad_status_text: str = "VAD 未启用"


@dataclass(frozen=True, slots=True)
class ProtocolState:
    last_client_json_redacted: str | None = None
    last_server_json_redacted: str | None = None
    last_protocol_event: str | None = None
    last_unknown_message_type: str | None = None
    last_protocol_error: str | None = None
    last_binary_size_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class RecoveryState:
    reconnect_attempt: int = 0
    last_reconnect_decision: str | None = None
    next_reconnect_at_ns: int | None = None
    runtime_error_count: int = 0
    manual_disconnect_requested: bool = False


@dataclass(frozen=True, slots=True)
class McpRuntimeState:
    last_tool_name: str | None = None
    last_tool_status: str | None = None
    last_request_id: str | None = None
    last_command_log_id: int | None = None
    last_confirmation_id: str | None = None
    real_tool_call_verified: bool = False


@dataclass(frozen=True, slots=True)
class RuntimeDiagnostics:
    gate_real_handshake_verified: bool = False
    gate_real_text_verified: bool = False
    gate_real_audio_upload_verified: bool = False
    gate_real_audio_playback_verified: bool = False
    last_event_name: str | None = None
    last_event_at_ns: int | None = None
    metrics_sample_count: int = 0


@dataclass(frozen=True, slots=True)
class AssistantError:
    code: str
    message: str
    category: AssistantErrorCategory
    recoverable: bool
    source_event: str
    occurred_at_ns: int
    details_redacted: str | None = None


class StateInvariantError(ValueError):
    """Raised when an AssistantState violates a frozen runtime invariant."""


@dataclass(frozen=True, slots=True)
class AssistantState:
    schema_version: int = 1
    phase: AssistantPhase = AssistantPhase.DISABLED
    enabled: bool = False
    runtime_mode: AssistantRuntimeMode = AssistantRuntimeMode.REAL
    connection: ConnectionState = ConnectionState()
    activation: ActivationState = ActivationState()
    identity: IdentityPublicState = IdentityPublicState()
    audio: AudioState = AudioState()
    conversation: ConversationState = ConversationState()
    protocol: ProtocolState = ProtocolState()
    recovery: RecoveryState = RecoveryState()
    mcp: McpRuntimeState = McpRuntimeState()
    diagnostics: RuntimeDiagnostics = RuntimeDiagnostics()
    capabilities: tuple[CapabilityState, ...] = field(
        default_factory=lambda: default_capabilities()
    )
    status_text: str = "助手已关闭"
    error: AssistantError | None = None
    last_event_at_ns: int | None = None

    @classmethod
    def disabled(
        cls,
        *,
        runtime_mode: AssistantRuntimeMode = AssistantRuntimeMode.REAL,
        now_ns: int | None = None,
    ) -> "AssistantState":
        state = cls(
            runtime_mode=runtime_mode,
            last_event_at_ns=now_ns,
            diagnostics=RuntimeDiagnostics(last_event_at_ns=now_ns),
        )
        validate_assistant_state(state)
        return state

    @property
    def is_connected(self) -> bool:
        return self.connection.status is AssistantConnectionStatus.CONNECTED and bool(
            self.connection.session_id
        )

    def capability_status(self, capability: AssistantCapability) -> CapabilityStatus:
        for item in self.capabilities:
            if item.name is capability:
                return item.status
        raise KeyError(capability.value)

    def validate(self) -> None:
        validate_assistant_state(self)


def default_capabilities() -> tuple[CapabilityState, ...]:
    active = CapabilityStatus.ACTIVE
    not_ready = CapabilityStatus.NOT_READY
    return (
        CapabilityState(AssistantCapability.RUNTIME_CORE, active, "2.1", "完整状态与单事件泵"),
        CapabilityState(AssistantCapability.FAKE_TRANSPORT, active, "2.1", "脚本化 Fake 链路"),
        CapabilityState(
            AssistantCapability.REAL_TRANSPORT, active, "2.3", "真实 WebSocket hello/session"
        ),
        CapabilityState(AssistantCapability.IDENTITY, active, "2.2", "稳定设备身份"),
        CapabilityState(AssistantCapability.ACTIVATION, active, "2.2", "Fake/Real OTA 与激活适配"),
        CapabilityState(AssistantCapability.TEXT_CONVERSATION, active, "2.1/2.4", "Fake 文本骨架"),
        CapabilityState(AssistantCapability.MANUAL_RECOVERY, active, "2.1", "手工重连骨架"),
        CapabilityState(AssistantCapability.AUTOMATIC_RECOVERY, not_ready, "2.5", "有界自动重连"),
        CapabilityState(
            AssistantCapability.ABORT_CURRENT_TURN,
            not_ready,
            "2.3/2.4",
            "当前回合中止协议",
        ),
        CapabilityState(AssistantCapability.PUSH_TO_TALK, not_ready, "3", "PTT 音频上行"),
        CapabilityState(AssistantCapability.TTS_PLAYBACK, not_ready, "4", "TTS 下行播放"),
        CapabilityState(
            AssistantCapability.MCP_PROTOCOL,
            active,
            "2.3/5",
            "MCP envelope typed route；工具执行仍 blocked",
        ),
        CapabilityState(AssistantCapability.MCP_NOTES, not_ready, "5", "便签工具闭环"),
        CapabilityState(
            AssistantCapability.STREAMING_CONVERSATION,
            not_ready,
            "6",
            "连续对话",
        ),
        CapabilityState(AssistantCapability.VAD, not_ready, "6", "语音活动检测"),
        CapabilityState(AssistantCapability.BARGE_IN, not_ready, "6", "简单打断"),
        CapabilityState(
            AssistantCapability.MICROPHONE_OWNERSHIP,
            not_ready,
            "3/6.5",
            "麦克风租约",
        ),
        CapabilityState(AssistantCapability.KWS, not_ready, "6.5", "唤醒词"),
        CapabilityState(
            AssistantCapability.SYSTEM_AUDIO_RECOVERY,
            not_ready,
            "6",
            "系统音频中断恢复",
        ),
        CapabilityState(AssistantCapability.METRICS_BASE, active, "2.1", "单调时钟基础打点"),
    )


def validate_assistant_state(state: AssistantState) -> None:
    if state.schema_version != 1:
        raise StateInvariantError(f"unsupported schema_version: {state.schema_version}")

    names = [item.name for item in state.capabilities]
    if len(names) != len(set(names)):
        raise StateInvariantError("capability registry contains duplicate names")

    if not state.enabled:
        if state.phase is not AssistantPhase.DISABLED:
            raise StateInvariantError("disabled assistant must use the disabled phase")
        if state.connection.status is not AssistantConnectionStatus.DISCONNECTED:
            raise StateInvariantError("disabled assistant cannot retain a connection")
        if state.connection.session_id is not None:
            raise StateInvariantError("disabled assistant cannot retain a session_id")
        if state.audio.status is not AssistantAudioStatus.IDLE:
            raise StateInvariantError("disabled assistant cannot record or play audio")
        if state.audio.microphone_owner is not MicrophoneOwner.NONE:
            raise StateInvariantError("disabled assistant cannot own the microphone")
        if state.recovery.next_reconnect_at_ns is not None:
            raise StateInvariantError("disabled assistant cannot retain a reconnect timer")

    if state.connection.status is AssistantConnectionStatus.CONNECTED:
        if not state.connection.session_id:
            raise StateInvariantError("connected status requires a non-empty session_id")
    elif state.connection.session_id is not None:
        raise StateInvariantError("session_id may exist only while connected")

    connected_phases = {
        AssistantPhase.CONNECTED,
        AssistantPhase.LISTENING,
        AssistantPhase.UPLOADING_AUDIO,
        AssistantPhase.THINKING,
        AssistantPhase.SPEAKING,
    }
    if state.phase in connected_phases and not state.is_connected:
        raise StateInvariantError(f"phase {state.phase.value} requires an active session")

    if state.phase in {AssistantPhase.LISTENING, AssistantPhase.UPLOADING_AUDIO}:
        if state.audio.microphone_owner is not MicrophoneOwner.ASSISTANT_CAPTURE:
            raise StateInvariantError("capture phases require the assistant microphone lease")

    if state.phase is AssistantPhase.SPEAKING:
        if state.audio.status is not AssistantAudioStatus.PLAYING:
            raise StateInvariantError("speaking phase requires playing audio")

    if not state.conversation.streaming_session_active:
        allowed = {
            StreamingConversationState.INACTIVE,
            StreamingConversationState.STOPPING,
            StreamingConversationState.ERROR,
        }
        if state.conversation.streaming_state not in allowed:
            raise StateInvariantError("inactive streaming session has an active streaming state")
    elif state.conversation.streaming_state is StreamingConversationState.INACTIVE:
        raise StateInvariantError("active streaming session cannot use the inactive state")

    counters = (
        state.audio.capture_generation,
        state.audio.playback_generation,
        state.audio.wakeword_generation,
        state.audio.microphone_lease_generation,
        state.audio.captured_frames,
        state.audio.encoded_frames,
        state.audio.uploaded_frames,
        state.audio.decoded_frames,
        state.audio.played_frames,
        state.conversation.streaming_generation,
        state.conversation.streaming_turn_index,
        state.conversation.barge_in_trigger_count,
        state.recovery.reconnect_attempt,
        state.recovery.runtime_error_count,
        state.diagnostics.metrics_sample_count,
    )
    if any(value < 0 for value in counters):
        raise StateInvariantError("runtime counters and generations cannot be negative")
