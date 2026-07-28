"""Pure Assistant Runtime reducer for Gate 2.1 and future runtime gates."""

from __future__ import annotations

from dataclasses import replace

from .effects import (
    AssistantEffect,
    CancelReconnect,
    CancelRuntimeEffects,
    CancelStreamingResponseTimeout,
    CloseTransport,
    EnsureIdentity,
    OpenTransport,
    ResetIdentity,
    RunActivation,
    ScheduleReconnect,
    ScheduleStreamingResponseTimeout,
    SendText,
    SetStreamingBargeIn,
    SetVoiceInteractionMode,
    StartPushToTalk,
    StartStreamingConversation,
    StopPushToTalk,
    StopStreamingConversation,
)
from .events import (
    AbortRequested,
    ActivationFailed,
    ActivationRequired,
    ActivationStarted,
    ActivationSucceeded,
    AssistantEvent,
    AssistantTextReceived,
    BinaryAudioReceived,
    AbortSent,
    AudioCaptureFailed,
    AudioCaptureStarted,
    AudioCaptureStopped,
    AudioCountersUpdated,
    AudioFailureSimulationRequested,
    AudioUplinkOverflow,
    BargeInTriggered,
    ClientHelloSent,
    ClientTextSent,
    ConnectRequested,
    ConnectionClosedSimulationRequested,
    ConnectionFailureSimulationRequested,
    DisableRequested,
    DisconnectRequested,
    EffectExecutionFailed,
    EnableRequested,
    EnsureIdentityRequested,
    FakeActivationRequested,
    IncomingToolCallSimulationRequested,
    IdentityReady,
    IdentityReset,
    KwsStateChanged,
    ListenStartSent,
    ListenStopSent,
    McpRequestCompleted,
    McpRequestReceived,
    MicrophoneLeaseChanged,
    ProtocolInvalidMessageReceived,
    ProtocolMessageObserved,
    ProtocolUnknownMessageReceived,
    PushToTalkStartRequested,
    PushToTalkStopRequested,
    PlaybackCountersUpdated,
    PlaybackEnded,
    PlaybackStarted,
    RealActivationRequested,
    ReconnectTimerFired,
    ReconnectRequested,
    ResetIdentityRequested,
    RuntimeOverloaded,
    ServerHelloReceived,
    ShutdownRequested,
    StreamingBargeInRequested,
    StreamingConversationStartRequested,
    StreamingConversationStopRequested,
    StreamingResponseTimeout,
    StreamingSessionStarted,
    StreamingSessionStopped,
    StreamingTurnChanged,
    StreamingTurnSubmitted,
    SystemAudioInterrupted,
    SystemAudioRecovered,
    TextSubmitted,
    TextTurnCompleted,
    TokenUsageReceived,
    ToolsListSimulationRequested,
    TtsStateReceived,
    VoiceActivityChanged,
    WakeWordDetected,
    TransportClosed,
    TransportFailed,
    TransportOpened,
    UseFakeRuntimeRequested,
    UseRealRuntimeRequested,
    VoiceInteractionModeRequested,
    VoiceTurnCompleted,
)
from .errors import AssistantErrorCode
from .network.reconnect_policy import ReconnectDecision, ReconnectPolicy
from .protocol import has_readable_transcript_text, merge_assistant_transcript
from .state import (
    AssistantActivationStatus,
    AssistantAudioStatus,
    AssistantCapability,
    AssistantConnectionStatus,
    AssistantEntrySource,
    AssistantError,
    AssistantErrorCategory,
    AssistantPhase,
    AssistantRuntimeMode,
    AssistantState,
    ActivationState,
    AudioState,
    ConnectionState,
    ConversationState,
    IdentityPublicState,
    MicrophoneOwner,
    StreamingConversationState,
    TokenUsageState,
    VoiceActivityState,
    VoiceInteractionMode,
)
from .transitions import Transition


class ConversationStateMachine:
    """Reduce one event into one immutable state replacement plus effects."""

    def __init__(self, reconnect_policy: ReconnectPolicy | None = None) -> None:
        self._reconnect_policy = reconnect_policy or ReconnectPolicy()

    def reduce(self, current: AssistantState, event: AssistantEvent) -> Transition:
        if isinstance(event, EnableRequested):
            return self._enable(current, event)
        if isinstance(event, DisableRequested):
            return self._disable(current, event, status_text="助手已关闭")
        if isinstance(event, ShutdownRequested):
            return self._disable(current, event, status_text="Assistant Runtime 已关闭")
        if isinstance(event, UseFakeRuntimeRequested):
            return self._switch_runtime(current, event, AssistantRuntimeMode.FAKE)
        if isinstance(event, UseRealRuntimeRequested):
            return self._switch_runtime(current, event, AssistantRuntimeMode.REAL)
        if isinstance(event, ConnectRequested):
            return self._connect(current, event)
        if isinstance(event, ReconnectRequested):
            return self._reconnect(current, event)
        if isinstance(event, DisconnectRequested):
            return self._disconnect(current, event)
        if isinstance(event, TextSubmitted):
            return self._submit_text(current, event)
        if isinstance(event, TransportOpened):
            return self._transport_opened(current, event)
        if isinstance(event, ClientHelloSent):
            return self._hello_sent(current, event)
        if isinstance(event, ServerHelloReceived):
            return self._hello_received(current, event)
        if isinstance(event, ClientTextSent):
            return self._client_text_sent(current, event)
        if isinstance(event, AssistantTextReceived):
            if event.turn_token == current.conversation.active_voice_turn_token:
                return self._voice_assistant_text(current, event)
            return self._assistant_text(current, event)
        if isinstance(event, TtsStateReceived):
            if event.turn_token == current.conversation.active_voice_turn_token:
                return self._voice_tts_state(current, event)
            return self._tts_state(current, event)
        if isinstance(event, TextTurnCompleted):
            return self._text_turn_completed(current, event)
        if isinstance(event, ProtocolMessageObserved):
            return self._protocol_observed(current, event)
        if isinstance(event, TokenUsageReceived):
            return self._token_usage_received(current, event)
        if isinstance(event, ProtocolUnknownMessageReceived):
            return self._protocol_unknown(current, event)
        if isinstance(event, ProtocolInvalidMessageReceived):
            return self._protocol_invalid(current, event)
        if isinstance(event, BinaryAudioReceived):
            return self._binary_audio(current, event)
        if isinstance(event, TransportClosed):
            return self._transport_closed(current, event)
        if isinstance(event, TransportFailed):
            return self._transport_failed(current, event)
        if isinstance(event, ConnectionClosedSimulationRequested):
            simulated = TransportClosed(
                at_ns=event.at_ns,
                generation=current.connection.connection_generation,
                code=event.code,
                reason=event.reason,
                expected=False,
            )
            return self._transport_closed(current, simulated)
        if isinstance(event, ConnectionFailureSimulationRequested):
            simulated = TransportFailed(
                at_ns=event.at_ns,
                generation=current.connection.connection_generation,
                message=event.message,
            )
            return self._transport_failed(current, simulated)
        if isinstance(event, IncomingToolCallSimulationRequested):
            return self._blocked_tool_call(current, event)
        if isinstance(event, ToolsListSimulationRequested):
            return self._tools_list_not_ready(current, event)
        if isinstance(event, AudioFailureSimulationRequested):
            return self._audio_failure(current, event)
        if isinstance(event, EffectExecutionFailed):
            return self._effect_failed(current, event)
        if isinstance(event, IdentityReady):
            return self._identity_ready(current, event)
        if isinstance(event, IdentityReset):
            return self._identity_reset(current, event)
        if isinstance(event, ActivationStarted):
            return self._activation_started(current, event)
        if isinstance(event, ActivationRequired):
            return self._activation_required(current, event)
        if isinstance(event, ActivationSucceeded):
            return self._activation_succeeded(current, event)
        if isinstance(event, ActivationFailed):
            return self._activation_failed(current, event)
        if isinstance(event, ReconnectTimerFired):
            return self._reconnect_timer_fired(current, event)
        if isinstance(event, VoiceInteractionModeRequested):
            return self._voice_interaction_mode_requested(current, event)
        if isinstance(event, StreamingBargeInRequested):
            return self._streaming_barge_in_requested(current, event)
        if isinstance(event, ListenStartSent):
            return self._listen_start_sent(current, event)
        if isinstance(event, ListenStopSent):
            return self._listen_stop_sent(current, event)
        if isinstance(event, AbortSent):
            return self._abort_sent(current, event)
        if isinstance(event, AudioCaptureStarted):
            return self._audio_capture_started(current, event)
        if isinstance(event, AudioCountersUpdated):
            return self._audio_counters_updated(current, event)
        if isinstance(event, AudioCaptureStopped):
            return self._audio_capture_stopped(current, event)
        if isinstance(event, AudioCaptureFailed):
            return self._audio_capture_failed(current, event)
        if isinstance(event, AudioUplinkOverflow):
            return self._audio_uplink_overflow(current, event)
        if isinstance(event, VoiceTurnCompleted):
            return self._voice_turn_completed(current, event)
        if isinstance(
            event,
            (PlaybackStarted, PlaybackEnded, PlaybackCountersUpdated),
        ):
            return self._not_ready(current, event, AssistantCapability.TTS_PLAYBACK)
        if isinstance(event, VoiceActivityChanged):
            return self._voice_activity_changed(current, event)
        if isinstance(event, StreamingSessionStarted):
            return self._streaming_session_started(current, event)
        if isinstance(event, StreamingTurnChanged):
            return self._streaming_turn_changed(current, event)
        if isinstance(event, StreamingTurnSubmitted):
            return self._streaming_turn_submitted(current, event)
        if isinstance(event, StreamingResponseTimeout):
            return self._streaming_response_timeout(current, event)
        if isinstance(event, StreamingSessionStopped):
            return self._streaming_session_stopped(current, event)
        if isinstance(event, BargeInTriggered):
            return self._not_ready(current, event, AssistantCapability.BARGE_IN)
        if isinstance(event, MicrophoneLeaseChanged):
            return self._microphone_lease_changed(current, event)
        if isinstance(event, (McpRequestReceived, McpRequestCompleted)):
            return self._not_ready(current, event, AssistantCapability.MCP_PROTOCOL)
        if isinstance(event, (WakeWordDetected, KwsStateChanged)):
            return self._not_ready(current, event, AssistantCapability.KWS)
        if isinstance(event, RuntimeOverloaded):
            return self._error(
                current,
                event,
                code=AssistantErrorCode.RUNTIME_OVERLOADED.value,
                message=event.message,
                category=AssistantErrorCategory.RUNTIME,
                recoverable=True,
            )
        if isinstance(event, PushToTalkStartRequested):
            return self._push_to_talk_start_requested(current, event)
        if isinstance(event, PushToTalkStopRequested):
            return self._push_to_talk_stop_requested(current, event)
        if isinstance(event, StreamingConversationStartRequested):
            return self._streaming_start_requested(current, event)
        if isinstance(event, StreamingConversationStopRequested):
            return self._streaming_stop_requested(current, event)
        if isinstance(event, AbortRequested):
            return self._not_ready(current, event, AssistantCapability.ABORT_CURRENT_TURN)
        if isinstance(event, (SystemAudioInterrupted, SystemAudioRecovered)):
            return self._not_ready(current, event, AssistantCapability.SYSTEM_AUDIO_RECOVERY)
        if isinstance(event, EnsureIdentityRequested):
            return self._ensure_identity(current, event)
        if isinstance(event, ResetIdentityRequested):
            return self._reset_identity(current, event)
        if isinstance(event, FakeActivationRequested):
            return self._request_activation(current, event, fake=True)
        if isinstance(event, RealActivationRequested):
            return self._request_activation(current, event, fake=False)
        return self._error(
            current,
            event,
            code="unknown_event",
            message=f"未识别的 Runtime 事件：{type(event).__name__}",
            category=AssistantErrorCategory.RUNTIME,
            recoverable=False,
        )

    def _voice_interaction_mode_requested(
        self,
        current: AssistantState,
        event: VoiceInteractionModeRequested,
    ) -> Transition:
        if current.conversation.preferred_voice_mode is event.mode:
            return self._transition(current, event)
        label = "按住说话" if event.mode is VoiceInteractionMode.HOLD_TO_TALK else "连续对话"
        if current.conversation.streaming_session_active:
            turn_token = (
                current.conversation.active_streaming_turn_token
                or current.conversation.active_voice_turn_token
                or current.conversation.last_completed_streaming_turn_token
            )
            state = replace(
                current,
                conversation=replace(
                    current.conversation,
                    preferred_voice_mode=event.mode,
                    streaming_state=StreamingConversationState.STOPPING,
                    streaming_response_deadline_ns=None,
                ),
                status_text=f"正在停止连续对话并切换为：{label}",
                error=None,
            )
            effects: list[AssistantEffect] = [CancelStreamingResponseTimeout()]
            if turn_token > 0:
                effects.append(
                    StopStreamingConversation(
                        connection_generation=current.connection.connection_generation,
                        streaming_generation=current.conversation.streaming_generation,
                        capture_generation=current.audio.capture_generation,
                        turn_token=turn_token,
                        requested_at_ns=event.at_ns,
                        reason="voice_mode_changed",
                        submit_audio=False,
                        end_session=True,
                    )
                )
            return self._transition(state, event, tuple(effects))
        if current.audio.status is AssistantAudioStatus.RECORDING:
            return self._error(
                current,
                event,
                code="voice_mode_change_busy",
                message="当前按住说话回合结束后才能切换默认语音模式",
                category=AssistantErrorCategory.CAPABILITY,
                recoverable=True,
                preserve_phase=True,
            )
        state = replace(
            current,
            conversation=replace(
                current.conversation,
                preferred_voice_mode=event.mode,
            ),
            status_text=f"默认语音模式已切换为：{label}",
            error=None,
        )
        return self._transition(
            state,
            event,
            (SetVoiceInteractionMode(mode=event.mode),),
        )

    def _streaming_barge_in_requested(
        self,
        current: AssistantState,
        event: StreamingBargeInRequested,
    ) -> Transition:
        state = replace(
            current,
            conversation=replace(
                current.conversation,
                streaming_barge_in_enabled=event.enabled,
            ),
            status_text=(
                "连续对话插话偏好已开启；Gate 4.2 前不会启动监听"
                if event.enabled
                else "连续对话插话偏好已关闭"
            ),
            error=None,
        )
        return self._transition(
            state,
            event,
            (SetStreamingBargeIn(enabled=event.enabled),),
        )

    def _streaming_start_requested(
        self,
        current: AssistantState,
        event: StreamingConversationStartRequested,
    ) -> Transition:
        if not event.permission_granted:
            return self._error(
                current,
                event,
                code=AssistantErrorCode.MICROPHONE_PERMISSION_DENIED.value,
                message="麦克风权限未授予",
                category=AssistantErrorCategory.AUDIO,
                recoverable=True,
                preserve_phase=True,
            )
        if not current.is_connected:
            return self._error(
                current,
                event,
                code=AssistantErrorCode.ASSISTANT_NOT_CONNECTED.value,
                message="助手未连接，不能开始连续对话",
                category=AssistantErrorCategory.TRANSPORT,
                recoverable=True,
                preserve_phase=True,
            )
        if (
            current.conversation.preferred_voice_mode
            is not VoiceInteractionMode.STREAMING_CONVERSATION
        ):
            return self._error(
                current,
                event,
                code=AssistantErrorCode.VOICE_MODE_MISMATCH.value,
                message="当前设置为按住说话模式",
                category=AssistantErrorCategory.CAPABILITY,
                recoverable=True,
                preserve_phase=True,
            )
        if (
            current.conversation.streaming_session_active
            or current.conversation.active_voice_turn_token is not None
            or current.conversation.active_text_turn_token is not None
            or current.audio.status is AssistantAudioStatus.RECORDING
            or current.phase is not AssistantPhase.CONNECTED
        ):
            return self._error(
                current,
                event,
                code=AssistantErrorCode.STREAMING_BUSY.value,
                message="已有对话回合正在运行",
                category=AssistantErrorCategory.AUDIO,
                recoverable=True,
                preserve_phase=True,
            )

        streaming_generation = current.conversation.streaming_generation + 1
        capture_generation = current.audio.capture_generation + 1
        turn_token = current.conversation.voice_turn_counter + 1
        turn_index = 1
        state = replace(
            current,
            audio=replace(
                current.audio,
                status=AssistantAudioStatus.IDLE,
                capture_generation=capture_generation,
                microphone_owner=MicrophoneOwner.NONE,
                active_capture_mode=None,
                captured_frames=0,
                encoded_frames=0,
                uploaded_frames=0,
                dropped_pcm_frames=0,
                uplink_overflow_count=0,
                last_audio_summary=None,
                first_pcm_latency_ms=None,
                first_opus_latency_ms=None,
                first_opus_upload_latency_ms=None,
                stop_listen_latency_ms=None,
                input_device_public_name=None,
            ),
            conversation=replace(
                current.conversation,
                active_entry_source=event.source,
                last_user_text=None,
                last_stt_text=None,
                last_assistant_text=None,
                last_assistant_source_type=None,
                assistant_reply_buffer="",
                voice_turn_counter=turn_token,
                active_voice_turn_token=turn_token,
                active_voice_turn_started_at_ns=event.at_ns,
                pending_voice_turn_completion_token=None,
                streaming_state=StreamingConversationState.STARTING,
                streaming_session_active=True,
                streaming_generation=streaming_generation,
                streaming_session_id=None,
                streaming_turn_index=turn_index,
                active_streaming_turn_token=turn_token,
                streaming_response_deadline_ns=None,
                vad_state=VoiceActivityState.WARMUP,
                vad_status_text="VAD 准备中",
            ),
            status_text="正在启动连续对话",
            error=None,
        )
        return self._transition(
            state,
            event,
            (
                StartStreamingConversation(
                    connection_generation=current.connection.connection_generation,
                    streaming_generation=streaming_generation,
                    capture_generation=capture_generation,
                    turn_token=turn_token,
                    turn_index=turn_index,
                    requested_at_ns=event.at_ns,
                    idle_timeout_ms=current.conversation.streaming_idle_timeout_ms,
                    source=event.source,
                    wake_keyword=event.wake_keyword,
                ),
            ),
        )

    def _streaming_stop_requested(
        self,
        current: AssistantState,
        event: StreamingConversationStopRequested,
    ) -> Transition:
        if not current.conversation.streaming_session_active:
            return self._transition(
                replace(current, status_text="当前没有连续对话会话", error=None),
                event,
            )
        turn_token = (
            current.conversation.active_streaming_turn_token
            or current.conversation.active_voice_turn_token
            or current.conversation.last_completed_streaming_turn_token
        )
        if turn_token <= 0:
            return self._transition(
                replace(current, status_text="连续对话已停止", error=None), event
            )
        state = replace(
            current,
            phase=(
                AssistantPhase.UPLOADING_AUDIO
                if current.audio.status is AssistantAudioStatus.RECORDING
                else AssistantPhase.CONNECTED
            ),
            conversation=replace(
                current.conversation,
                streaming_state=StreamingConversationState.STOPPING,
                streaming_response_deadline_ns=None,
            ),
            status_text="正在停止连续对话",
            error=None,
        )
        return self._transition(
            state,
            event,
            (
                CancelStreamingResponseTimeout(),
                StopStreamingConversation(
                    connection_generation=current.connection.connection_generation,
                    streaming_generation=current.conversation.streaming_generation,
                    capture_generation=current.audio.capture_generation,
                    turn_token=turn_token,
                    requested_at_ns=event.at_ns,
                    reason=event.reason,
                    submit_audio=False,
                    end_session=True,
                ),
            ),
        )

    def _streaming_session_started(
        self, current: AssistantState, event: StreamingSessionStarted
    ) -> Transition:
        if self._is_stale_connection_event(current, event.connection_generation):
            return Transition.unchanged(current)
        if (
            not current.conversation.streaming_session_active
            or event.generation != current.conversation.streaming_generation
            or event.capture_generation != current.audio.capture_generation
            or event.turn_token != current.conversation.active_streaming_turn_token
        ):
            return Transition.unchanged(current)
        state = replace(
            current,
            conversation=replace(
                current.conversation,
                streaming_session_id=event.session_id,
                streaming_turn_index=event.turn_index,
                streaming_state=StreamingConversationState.LISTENING_FOR_SPEECH,
                vad_state=VoiceActivityState.WARMUP,
                vad_status_text="VAD 预热中",
            ),
            status_text="连续对话已启动，正在准备聆听",
            error=None,
        )
        return self._transition(state, event)

    def _voice_activity_changed(
        self, current: AssistantState, event: VoiceActivityChanged
    ) -> Transition:
        if self._is_stale_connection_event(current, event.connection_generation):
            return Transition.unchanged(current)
        if (
            not current.conversation.streaming_session_active
            or current.audio.status is not AssistantAudioStatus.RECORDING
            or current.conversation.streaming_state
            not in {
                StreamingConversationState.STARTING,
                StreamingConversationState.LISTENING_FOR_SPEECH,
                StreamingConversationState.USER_SPEAKING,
            }
            or event.streaming_generation != current.conversation.streaming_generation
            or event.generation != current.audio.capture_generation
            or event.turn_token != current.conversation.active_streaming_turn_token
        ):
            return Transition.unchanged(current)

        conversation = replace(
            current.conversation,
            vad_state=event.state,
            vad_status_text=event.status_text,
        )
        phase = current.phase
        effects: tuple[AssistantEffect, ...] = ()
        diagnostics = current.diagnostics
        if event.state in {VoiceActivityState.WARMUP, VoiceActivityState.WAITING_FOR_SPEECH}:
            conversation = replace(
                conversation,
                streaming_state=StreamingConversationState.LISTENING_FOR_SPEECH,
            )
            phase = AssistantPhase.LISTENING
        elif event.state in {
            VoiceActivityState.SPEECH_DETECTED,
            VoiceActivityState.SPEECH_ACTIVE,
        }:
            conversation = replace(
                conversation,
                streaming_state=StreamingConversationState.USER_SPEAKING,
            )
            phase = AssistantPhase.LISTENING
            if event.state is VoiceActivityState.SPEECH_DETECTED:
                diagnostics = replace(
                    diagnostics,
                    vad_speech_started_count=diagnostics.vad_speech_started_count + 1,
                )
        elif event.state is VoiceActivityState.END_OF_SPEECH:
            if current.conversation.streaming_state is StreamingConversationState.SUBMITTING_TURN:
                return Transition.unchanged(current)
            conversation = replace(
                conversation,
                streaming_state=StreamingConversationState.SUBMITTING_TURN,
            )
            phase = AssistantPhase.UPLOADING_AUDIO
            diagnostics = replace(
                diagnostics,
                vad_speech_ended_count=diagnostics.vad_speech_ended_count + 1,
            )
            effects = (
                StopStreamingConversation(
                    connection_generation=current.connection.connection_generation,
                    streaming_generation=current.conversation.streaming_generation,
                    capture_generation=current.audio.capture_generation,
                    turn_token=event.turn_token,
                    requested_at_ns=event.at_ns,
                    reason="vad_end_of_speech",
                    submit_audio=True,
                    end_session=False,
                ),
            )
        elif event.state is VoiceActivityState.NO_SPEECH_TIMEOUT:
            conversation = replace(
                conversation,
                streaming_state=StreamingConversationState.STOPPING,
            )
            phase = AssistantPhase.UPLOADING_AUDIO
            effects = (
                StopStreamingConversation(
                    connection_generation=current.connection.connection_generation,
                    streaming_generation=current.conversation.streaming_generation,
                    capture_generation=current.audio.capture_generation,
                    turn_token=event.turn_token,
                    requested_at_ns=event.at_ns,
                    reason="streaming_no_speech_timeout",
                    submit_audio=False,
                    end_session=True,
                ),
            )
        state = replace(
            current,
            phase=phase,
            conversation=conversation,
            diagnostics=diagnostics,
            status_text=event.status_text,
            error=None,
        )
        return self._transition(state, event, effects)

    def _streaming_turn_changed(
        self, current: AssistantState, event: StreamingTurnChanged
    ) -> Transition:
        if (
            event.generation != current.conversation.streaming_generation
            or event.turn_token != current.conversation.active_streaming_turn_token
        ):
            return Transition.unchanged(current)
        return self._transition(
            replace(
                current,
                conversation=replace(
                    current.conversation,
                    streaming_turn_index=event.turn_index,
                    streaming_state=event.state,
                ),
            ),
            event,
        )

    def _streaming_turn_submitted(
        self, current: AssistantState, event: StreamingTurnSubmitted
    ) -> Transition:
        if self._is_stale_connection_event(current, event.connection_generation):
            return Transition.unchanged(current)
        if (
            event.generation != current.conversation.streaming_generation
            or event.capture_generation != current.audio.capture_generation
            or event.turn_token != current.conversation.active_streaming_turn_token
        ):
            return Transition.unchanged(current)
        deadline = event.at_ns + current.conversation.streaming_response_timeout_ms * 1_000_000
        state = replace(
            current,
            phase=AssistantPhase.THINKING,
            conversation=replace(
                current.conversation,
                streaming_state=StreamingConversationState.THINKING,
                streaming_response_deadline_ns=deadline,
                vad_state=VoiceActivityState.DISABLED,
                vad_status_text="本轮已自动提交",
            ),
            diagnostics=replace(
                current.diagnostics,
                gate_real_streaming_uplink_verified=(
                    current.diagnostics.gate_real_streaming_uplink_verified
                    or (
                        current.runtime_mode is AssistantRuntimeMode.REAL
                        and event.uploaded_frames > 0
                        and event.speech_seen
                    )
                ),
            ),
            status_text="连续对话语音已自动提交，等待助手回复",
            error=None,
        )
        return self._transition(
            state,
            event,
            (
                ScheduleStreamingResponseTimeout(
                    streaming_generation=event.generation,
                    turn_token=event.turn_token,
                    delay_seconds=current.conversation.streaming_response_timeout_ms / 1000.0,
                ),
            ),
        )

    def _streaming_response_timeout(
        self, current: AssistantState, event: StreamingResponseTimeout
    ) -> Transition:
        if (
            not current.conversation.streaming_session_active
            or event.generation != current.conversation.streaming_generation
            or event.turn_token != current.conversation.active_streaming_turn_token
        ):
            return Transition.unchanged(current)
        state = replace(
            current,
            phase=AssistantPhase.ERROR,
            conversation=replace(
                current.conversation,
                streaming_state=StreamingConversationState.ERROR,
                streaming_response_deadline_ns=None,
            ),
        )
        return self._error(
            state,
            event,
            code=AssistantErrorCode.STREAMING_RESPONSE_TIMEOUT.value,
            message="连续对话等待助手回复超时",
            category=AssistantErrorCategory.RUNTIME,
            recoverable=True,
            effects=(
                StopStreamingConversation(
                    connection_generation=current.connection.connection_generation,
                    streaming_generation=current.conversation.streaming_generation,
                    capture_generation=current.audio.capture_generation,
                    turn_token=event.turn_token,
                    requested_at_ns=event.at_ns,
                    reason="streaming_response_timeout",
                    submit_audio=False,
                    end_session=True,
                ),
            ),
            preserve_phase=True,
        )

    def _streaming_session_stopped(
        self, current: AssistantState, event: StreamingSessionStopped
    ) -> Transition:
        if event.generation != current.conversation.streaming_generation:
            return Transition.unchanged(current)
        conversation = replace(
            current.conversation,
            active_entry_source=None,
            active_voice_turn_token=None,
            active_voice_turn_started_at_ns=None,
            pending_voice_turn_completion_token=None,
            streaming_state=StreamingConversationState.INACTIVE,
            streaming_session_active=False,
            streaming_session_id=None,
            active_streaming_turn_token=None,
            streaming_response_deadline_ns=None,
            vad_state=VoiceActivityState.DISABLED,
            vad_status_text="VAD 未启用",
        )
        state = replace(
            current,
            phase=AssistantPhase.CONNECTED if current.is_connected else current.phase,
            audio=replace(
                current.audio,
                status=AssistantAudioStatus.IDLE,
                microphone_owner=MicrophoneOwner.NONE,
                active_capture_mode=None,
            ),
            conversation=conversation,
            status_text=(
                "连续对话因未检测到语音而结束"
                if event.reason == "streaming_no_speech_timeout"
                else "连续对话已停止"
            ),
            error=(current.error if event.reason == "streaming_response_timeout" else None),
        )
        effects: list[AssistantEffect] = [CancelStreamingResponseTimeout()]
        if event.reason == "voice_mode_changed":
            effects.append(SetVoiceInteractionMode(mode=current.conversation.preferred_voice_mode))
        return self._transition(state, event, tuple(effects))

    def _push_to_talk_start_requested(
        self,
        current: AssistantState,
        event: PushToTalkStartRequested,
    ) -> Transition:
        if not event.permission_granted:
            return self._error(
                current,
                event,
                code=AssistantErrorCode.MICROPHONE_PERMISSION_DENIED.value,
                message="麦克风权限未授予",
                category=AssistantErrorCategory.AUDIO,
                recoverable=True,
                preserve_phase=True,
            )
        if not current.is_connected:
            return self._error(
                current,
                event,
                code=AssistantErrorCode.ASSISTANT_NOT_CONNECTED.value,
                message="助手未连接，不能开始按住说话",
                category=AssistantErrorCategory.TRANSPORT,
                recoverable=True,
                preserve_phase=True,
            )
        if current.conversation.preferred_voice_mode is not VoiceInteractionMode.HOLD_TO_TALK:
            return self._error(
                current,
                event,
                code=AssistantErrorCode.VOICE_MODE_MISMATCH.value,
                message="当前设置为连续对话模式",
                category=AssistantErrorCategory.CAPABILITY,
                recoverable=True,
                preserve_phase=True,
            )
        if (
            current.conversation.active_voice_turn_token is not None
            or current.conversation.active_text_turn_token is not None
            or current.audio.status is AssistantAudioStatus.RECORDING
        ):
            return self._error(
                current,
                event,
                code=AssistantErrorCode.PUSH_TO_TALK_BUSY.value,
                message="已有对话回合正在运行",
                category=AssistantErrorCategory.AUDIO,
                recoverable=True,
                preserve_phase=True,
            )
        if current.phase is not AssistantPhase.CONNECTED:
            return self._error(
                current,
                event,
                code=AssistantErrorCode.PUSH_TO_TALK_BUSY.value,
                message="助手当前状态不能开始录音",
                category=AssistantErrorCategory.AUDIO,
                recoverable=True,
                preserve_phase=True,
            )

        capture_generation = current.audio.capture_generation + 1
        turn_token = current.conversation.voice_turn_counter + 1
        state = replace(
            current,
            phase=AssistantPhase.CONNECTED,
            audio=replace(
                current.audio,
                status=AssistantAudioStatus.IDLE,
                capture_generation=capture_generation,
                microphone_owner=MicrophoneOwner.NONE,
                active_capture_mode=None,
                captured_frames=0,
                encoded_frames=0,
                uploaded_frames=0,
                dropped_pcm_frames=0,
                uplink_overflow_count=0,
                last_audio_summary=None,
                push_to_talk_stop_latency_ms=None,
                first_pcm_latency_ms=None,
                first_opus_latency_ms=None,
                first_opus_upload_latency_ms=None,
                stop_listen_latency_ms=None,
                input_device_public_name=None,
            ),
            conversation=replace(
                current.conversation,
                active_entry_source=AssistantEntrySource.PUSH_TO_TALK,
                last_user_text=None,
                last_stt_text=None,
                last_assistant_text=None,
                last_assistant_source_type=None,
                assistant_reply_buffer="",
                voice_turn_counter=turn_token,
                active_voice_turn_token=turn_token,
                active_voice_turn_started_at_ns=event.at_ns,
                pending_voice_turn_completion_token=None,
            ),
            status_text="正在准备麦克风和语音上行",
            error=None,
        )
        return self._transition(
            state,
            event,
            (
                StartPushToTalk(
                    connection_generation=current.connection.connection_generation,
                    generation=capture_generation,
                    turn_token=turn_token,
                    requested_at_ns=event.at_ns,
                ),
            ),
        )

    def _push_to_talk_stop_requested(
        self,
        current: AssistantState,
        event: PushToTalkStopRequested,
    ) -> Transition:
        turn_token = current.conversation.active_voice_turn_token
        if (
            turn_token is None
            or current.conversation.active_entry_source is not AssistantEntrySource.PUSH_TO_TALK
        ):
            return self._transition(
                replace(current, status_text="当前没有按住说话回合", error=None),
                event,
            )
        state = replace(
            current,
            phase=AssistantPhase.UPLOADING_AUDIO,
            status_text="正在结束录音并提交语音",
            error=None,
        )
        return self._transition(
            state,
            event,
            (
                StopPushToTalk(
                    connection_generation=current.connection.connection_generation,
                    generation=current.audio.capture_generation,
                    turn_token=turn_token,
                    requested_at_ns=event.at_ns,
                ),
            ),
        )

    def _listen_start_sent(self, current: AssistantState, event: ListenStartSent) -> Transition:
        if not self._matches_voice_event(
            current, event.generation, event.capture_generation, event.turn_token
        ):
            return Transition.unchanged(current)
        state = replace(
            current,
            protocol=replace(
                current.protocol,
                last_client_json_redacted=event.raw_json_redacted,
                last_protocol_event="ListenStartSent",
                last_protocol_error=None,
            ),
            status_text="语音监听已开始，等待麦克风首帧",
            error=None,
        )
        return self._transition(state, event)

    def _listen_stop_sent(self, current: AssistantState, event: ListenStopSent) -> Transition:
        if not self._matches_voice_event(
            current, event.generation, event.capture_generation, event.turn_token
        ):
            return Transition.unchanged(current)
        state = replace(
            current,
            protocol=replace(
                current.protocol,
                last_client_json_redacted=event.raw_json_redacted,
                last_protocol_event="ListenStopSent",
                last_protocol_error=None,
            ),
            status_text="语音已提交，等待识别和回复",
            error=None,
        )
        return self._transition(state, event)

    def _abort_sent(self, current: AssistantState, event: AbortSent) -> Transition:
        if self._is_stale_connection_event(current, event.generation):
            return Transition.unchanged(current)
        state = replace(
            current,
            protocol=replace(
                current.protocol,
                last_client_json_redacted=event.raw_json_redacted,
                last_protocol_event=f"AbortSent:{event.reason}",
                last_protocol_error=None,
            ),
            status_text=f"语音回合已中止：{event.reason}",
        )
        return self._transition(state, event)

    def _audio_capture_started(
        self,
        current: AssistantState,
        event: AudioCaptureStarted,
    ) -> Transition:
        if not self._matches_voice_event(
            current, event.connection_generation, event.generation, event.turn_token
        ):
            return Transition.unchanged(current)
        is_streaming = (
            current.conversation.streaming_session_active
            and current.conversation.active_streaming_turn_token == event.turn_token
        )
        conversation = current.conversation
        if is_streaming:
            conversation = replace(
                conversation,
                streaming_state=StreamingConversationState.LISTENING_FOR_SPEECH,
                vad_state=VoiceActivityState.WARMUP,
                vad_status_text="VAD 预热中",
            )
        state = replace(
            current,
            phase=AssistantPhase.LISTENING,
            audio=replace(
                current.audio,
                status=AssistantAudioStatus.RECORDING,
                input_device_public_name=event.input_device_public_name,
                microphone_owner=MicrophoneOwner.ASSISTANT_CAPTURE,
                microphone_lease_generation=current.audio.microphone_lease_generation + 1,
                active_capture_mode=("streaming_conversation" if is_streaming else "push_to_talk"),
            ),
            conversation=conversation,
            status_text=("连续对话正在聆听" if is_streaming else "正在聆听，松开后提交"),
            error=None,
        )
        return self._transition(state, event)

    def _audio_counters_updated(
        self,
        current: AssistantState,
        event: AudioCountersUpdated,
    ) -> Transition:
        if not self._matches_voice_event(
            current, event.connection_generation, event.generation, event.turn_token
        ):
            return Transition.unchanged(current)
        is_streaming = current.conversation.streaming_session_active
        state = replace(
            current,
            audio=replace(
                current.audio,
                captured_frames=event.captured_frames,
                encoded_frames=event.encoded_frames,
                uploaded_frames=event.uploaded_frames,
                dropped_pcm_frames=event.dropped_pcm_frames,
                uplink_overflow_count=event.uplink_overflow_count,
                first_pcm_latency_ms=event.first_pcm_latency_ms,
                first_opus_latency_ms=event.first_opus_latency_ms,
                first_opus_upload_latency_ms=event.first_opus_upload_latency_ms,
            ),
            diagnostics=replace(
                current.diagnostics,
                gate_real_audio_upload_verified=(
                    current.diagnostics.gate_real_audio_upload_verified
                    or (
                        current.runtime_mode is AssistantRuntimeMode.REAL
                        and event.uploaded_frames > 0
                    )
                ),
            ),
            status_text=(
                f"连续对话聆听中 · 已上传 {event.uploaded_frames} 帧"
                if is_streaming
                else f"正在聆听 · 已上传 {event.uploaded_frames} 帧"
            ),
            error=None,
        )
        return self._transition(state, event)

    def _audio_capture_stopped(
        self,
        current: AssistantState,
        event: AudioCaptureStopped,
    ) -> Transition:
        if self._is_stale_connection_event(current, event.connection_generation):
            return Transition.unchanged(current)
        if event.generation != current.audio.capture_generation:
            return Transition.unchanged(current)
        active = current.conversation.active_voice_turn_token == event.turn_token
        already_completed = current.conversation.last_completed_voice_turn_token >= event.turn_token
        if not active and not already_completed:
            return Transition.unchanged(current)
        audio = replace(
            current.audio,
            status=AssistantAudioStatus.IDLE,
            microphone_owner=MicrophoneOwner.NONE,
            active_capture_mode=None,
            captured_frames=event.captured_frames,
            encoded_frames=event.encoded_frames,
            uploaded_frames=event.uploaded_frames,
            dropped_pcm_frames=event.dropped_pcm_frames,
            uplink_overflow_count=event.uplink_overflow_count,
            last_audio_summary=event.summary,
            push_to_talk_stop_latency_ms=event.stop_latency_ms,
            first_pcm_latency_ms=event.first_pcm_latency_ms,
            first_opus_latency_ms=event.first_opus_latency_ms,
            first_opus_upload_latency_ms=event.first_opus_upload_latency_ms,
            stop_listen_latency_ms=event.stop_listen_latency_ms,
            input_device_public_name=event.input_device_public_name,
        )
        if current.conversation.streaming_session_active:
            response_already_observed = (
                current.conversation.streaming_state
                is StreamingConversationState.WAITING_FOR_NEXT_TURN
                or current.conversation.pending_voice_turn_completion_token == event.turn_token
            )
            conversation = replace(
                current.conversation,
                streaming_state=(
                    StreamingConversationState.WAITING_FOR_NEXT_TURN
                    if response_already_observed
                    else (
                        StreamingConversationState.SUBMITTING_TURN
                        if event.useful_audio and event.stop_sent
                        else StreamingConversationState.STOPPING
                    )
                ),
                vad_state=VoiceActivityState.DISABLED,
                vad_status_text=(
                    "本轮已收到回复"
                    if response_already_observed
                    else ("本轮已停止采集" if event.useful_audio else "未检测到有效语音")
                ),
            )
            effects: tuple[AssistantEffect, ...] = ()
            if response_already_observed:
                conversation = replace(
                    conversation,
                    active_voice_turn_token=None,
                    active_voice_turn_started_at_ns=None,
                    pending_voice_turn_completion_token=None,
                    last_completed_voice_turn_token=max(
                        conversation.last_completed_voice_turn_token,
                        event.turn_token,
                    ),
                    last_voice_turn_completed_at_ns=event.at_ns,
                    active_streaming_turn_token=None,
                    last_completed_streaming_turn_token=max(
                        conversation.last_completed_streaming_turn_token,
                        event.turn_token,
                    ),
                    streaming_response_deadline_ns=None,
                )
                effects = (CancelStreamingResponseTimeout(),)
            state = replace(
                current,
                phase=(
                    AssistantPhase.CONNECTED
                    if response_already_observed or not event.useful_audio or not event.stop_sent
                    else AssistantPhase.THINKING
                ),
                audio=audio,
                conversation=conversation,
                diagnostics=replace(
                    current.diagnostics,
                    gate_real_audio_upload_verified=(
                        current.diagnostics.gate_real_audio_upload_verified
                        or (
                            current.runtime_mode is AssistantRuntimeMode.REAL
                            and event.uploaded_frames > 0
                        )
                    ),
                    gate_real_streaming_uplink_verified=(
                        current.diagnostics.gate_real_streaming_uplink_verified
                        or (
                            current.runtime_mode is AssistantRuntimeMode.REAL
                            and event.uploaded_frames > 0
                            and event.speech_seen
                            and event.stop_sent
                        )
                    ),
                ),
                status_text=(
                    "连续对话本轮已收到回复"
                    if response_already_observed
                    else (
                        "连续对话语音已提交，等待识别和回复"
                        if event.useful_audio and event.stop_sent
                        else "连续对话本轮没有有效语音"
                    )
                ),
                error=None,
            )
            return self._transition(state, event, effects)

        conversation = current.conversation
        phase = current.phase
        status_text = "语音已提交，等待识别和回复"
        pending_completed = conversation.pending_voice_turn_completion_token == event.turn_token
        if pending_completed or not event.useful_audio:
            conversation = replace(
                conversation,
                active_voice_turn_token=None,
                active_voice_turn_started_at_ns=None,
                pending_voice_turn_completion_token=None,
                last_completed_voice_turn_token=max(
                    conversation.last_completed_voice_turn_token,
                    event.turn_token,
                ),
                last_voice_turn_completed_at_ns=event.at_ns,
                active_entry_source=None,
            )
            phase = AssistantPhase.CONNECTED if current.is_connected else current.phase
            status_text = (
                "没有检测到有效语音，本轮已结束" if not event.useful_audio else "语音回合已完成"
            )
        elif active:
            phase = AssistantPhase.THINKING
        else:
            phase = AssistantPhase.CONNECTED if current.is_connected else current.phase
            status_text = "语音回合已完成"
        state = replace(
            current,
            phase=phase,
            audio=audio,
            conversation=conversation,
            diagnostics=replace(
                current.diagnostics,
                gate_real_audio_upload_verified=(
                    current.diagnostics.gate_real_audio_upload_verified
                    or (
                        current.runtime_mode is AssistantRuntimeMode.REAL
                        and event.uploaded_frames > 0
                    )
                ),
            ),
            status_text=status_text,
            error=None,
        )
        return self._transition(state, event)

    def _audio_capture_failed(
        self,
        current: AssistantState,
        event: AudioCaptureFailed,
    ) -> Transition:
        if self._is_stale_connection_event(current, event.connection_generation):
            return Transition.unchanged(current)
        if event.generation != current.audio.capture_generation:
            return Transition.unchanged(current)
        conversation = replace(
            current.conversation,
            active_entry_source=None,
            active_voice_turn_token=None,
            active_voice_turn_started_at_ns=None,
            pending_voice_turn_completion_token=None,
        )
        if current.conversation.streaming_session_active:
            conversation = replace(
                conversation,
                streaming_state=StreamingConversationState.ERROR,
                streaming_session_active=False,
                streaming_session_id=None,
                active_streaming_turn_token=None,
                streaming_response_deadline_ns=None,
                vad_state=VoiceActivityState.DISABLED,
                vad_status_text="连续对话音频失败",
            )
        cleared = replace(
            current,
            phase=AssistantPhase.CONNECTED if current.is_connected else AssistantPhase.IDLE,
            audio=self._idle_audio(
                current.audio,
                invalidate_capture=True,
                invalidate_microphone_lease=True,
            ),
            conversation=conversation,
        )
        return self._error(
            cleared,
            event,
            code=event.code or AssistantErrorCode.AUDIO_CAPTURE_FAILED.value,
            message=event.message,
            category=AssistantErrorCategory.AUDIO,
            recoverable=True,
            effects=(CancelRuntimeEffects(reason="audio_capture_failed"),),
            preserve_phase=True,
        )

    def _audio_uplink_overflow(
        self,
        current: AssistantState,
        event: AudioUplinkOverflow,
    ) -> Transition:
        failed = AudioCaptureFailed(
            at_ns=event.at_ns,
            generation=event.generation,
            connection_generation=event.connection_generation,
            turn_token=event.turn_token,
            code=AssistantErrorCode.AUDIO_UPLINK_OVERFLOW.value,
            message=event.message,
        )
        return self._audio_capture_failed(current, failed)

    def _voice_assistant_text(
        self,
        current: AssistantState,
        event: AssistantTextReceived,
    ) -> Transition:
        if not self._matches_voice_protocol_event(
            current, event.generation, event.turn_token, event.session_id
        ):
            return Transition.unchanged(current)
        source_type = event.source_type.strip().lower() or "text"
        text = event.text.strip()
        protocol = replace(
            current.protocol,
            last_server_json_redacted=event.raw_json_redacted,
            last_protocol_event=f"VoiceAssistantText:{source_type}",
            last_protocol_error=None,
        )
        if source_type == "stt":
            state = replace(
                current,
                phase=AssistantPhase.THINKING,
                conversation=replace(
                    current.conversation,
                    last_user_text=text or None,
                    last_stt_text=text or None,
                ),
                protocol=protocol,
                status_text="语音识别完成，正在等待助手回复",
                error=None,
            )
            return self._transition(state, event)
        if not has_readable_transcript_text(text):
            return self._transition(
                replace(current, protocol=protocol, status_text="收到语音回复状态"),
                event,
            )
        merged = merge_assistant_transcript(current.conversation.assistant_reply_buffer, text)
        conversation = replace(
            current.conversation,
            last_assistant_text=merged,
            last_assistant_source_type=source_type,
            assistant_reply_buffer=merged,
        )
        effects: tuple[AssistantEffect, ...] = ()
        status_text = "收到语音回合助手回复"
        if current.conversation.streaming_session_active:
            conversation = replace(
                conversation,
                streaming_state=StreamingConversationState.WAITING_FOR_NEXT_TURN,
                streaming_response_deadline_ns=None,
            )
            effects = (CancelStreamingResponseTimeout(),)
            status_text = "连续对话本轮已收到回复；Gate 4.2 前不会自动开启下一轮"
        state = replace(
            current,
            conversation=conversation,
            protocol=protocol,
            diagnostics=replace(
                current.diagnostics,
                gate_real_audio_response_verified=(
                    current.diagnostics.gate_real_audio_response_verified
                    or current.runtime_mode is AssistantRuntimeMode.REAL
                ),
            ),
            status_text=status_text,
            error=None,
        )
        return self._transition(state, event, effects)

    def _voice_tts_state(
        self,
        current: AssistantState,
        event: TtsStateReceived,
    ) -> Transition:
        if not self._matches_voice_protocol_event(
            current, event.generation, event.turn_token, event.session_id
        ):
            return Transition.unchanged(current)
        text = (event.text or "").strip()
        conversation = current.conversation
        if has_readable_transcript_text(text):
            merged = merge_assistant_transcript(conversation.assistant_reply_buffer, text)
            conversation = replace(
                conversation,
                last_assistant_text=merged,
                last_assistant_source_type="tts",
                assistant_reply_buffer=merged,
            )
        effects: tuple[AssistantEffect, ...] = ()
        if current.conversation.streaming_session_active:
            conversation = replace(
                conversation,
                streaming_state=StreamingConversationState.WAITING_FOR_NEXT_TURN,
                streaming_response_deadline_ns=None,
            )
            effects = (CancelStreamingResponseTimeout(),)
        state = replace(
            current,
            conversation=conversation,
            protocol=replace(
                current.protocol,
                last_server_json_redacted=event.raw_json_redacted,
                last_protocol_event=f"VoiceTtsState:{event.state}",
                last_protocol_error=None,
            ),
            diagnostics=replace(
                current.diagnostics,
                gate_real_audio_response_verified=(
                    current.diagnostics.gate_real_audio_response_verified
                    or (
                        current.runtime_mode is AssistantRuntimeMode.REAL
                        and (has_readable_transcript_text(text) or bool(event.state.strip()))
                    )
                ),
            ),
            status_text=(
                "连续对话收到回复状态；Gate 4 前不播放"
                if current.conversation.streaming_session_active
                else f"收到语音回合 TTS state={event.state}；Gate 4 前不播放"
            ),
            error=None,
        )
        return self._transition(state, event, effects)

    def _voice_turn_completed(
        self,
        current: AssistantState,
        event: VoiceTurnCompleted,
    ) -> Transition:
        if self._is_stale_connection_event(current, event.generation):
            return Transition.unchanged(current)
        if event.capture_generation != current.audio.capture_generation:
            return Transition.unchanged(current)
        if event.turn_token != current.conversation.active_voice_turn_token:
            return Transition.unchanged(current)

        capture_cleanup_pending = (
            current.audio.status is AssistantAudioStatus.RECORDING
            or current.audio.microphone_owner is MicrophoneOwner.ASSISTANT_CAPTURE
        )
        if capture_cleanup_pending:
            conversation = replace(
                current.conversation,
                pending_voice_turn_completion_token=event.turn_token,
            )
            phase = current.phase
            audio = current.audio
            status_text = "服务端回复已完成，正在释放麦克风"
            effects: tuple[AssistantEffect, ...] = ()
        elif current.conversation.streaming_session_active:
            conversation = replace(
                current.conversation,
                active_voice_turn_token=None,
                active_voice_turn_started_at_ns=None,
                pending_voice_turn_completion_token=None,
                last_completed_voice_turn_token=max(
                    current.conversation.last_completed_voice_turn_token, event.turn_token
                ),
                last_voice_turn_completed_at_ns=event.at_ns,
                active_streaming_turn_token=None,
                last_completed_streaming_turn_token=max(
                    current.conversation.last_completed_streaming_turn_token,
                    event.turn_token,
                ),
                streaming_state=StreamingConversationState.WAITING_FOR_NEXT_TURN,
                streaming_response_deadline_ns=None,
            )
            phase = AssistantPhase.CONNECTED if current.is_connected else current.phase
            audio = replace(
                current.audio,
                status=AssistantAudioStatus.IDLE,
                microphone_owner=MicrophoneOwner.NONE,
                active_capture_mode=None,
            )
            status_text = "连续对话本轮完成；Gate 4.2 前等待用户停止"
            effects = (CancelStreamingResponseTimeout(),)
        else:
            conversation = replace(
                current.conversation,
                active_voice_turn_token=None,
                active_voice_turn_started_at_ns=None,
                pending_voice_turn_completion_token=None,
                last_completed_voice_turn_token=event.turn_token,
                last_voice_turn_completed_at_ns=event.at_ns,
                active_entry_source=None,
            )
            phase = AssistantPhase.CONNECTED if current.is_connected else current.phase
            audio = replace(
                current.audio,
                status=AssistantAudioStatus.IDLE,
                microphone_owner=MicrophoneOwner.NONE,
                active_capture_mode=None,
            )
            status_text = (
                f"语音回合 {event.turn_token} 完成"
                if event.had_stt_text or event.had_assistant_text
                else f"语音回合 {event.turn_token} 已结束"
            )
            effects = ()

        state = replace(
            current,
            phase=phase,
            audio=audio,
            conversation=conversation,
            diagnostics=replace(
                current.diagnostics,
                gate_real_audio_response_verified=(
                    current.diagnostics.gate_real_audio_response_verified
                    or (
                        current.runtime_mode is AssistantRuntimeMode.REAL
                        and event.had_assistant_text
                    )
                ),
            ),
            status_text=status_text,
            error=None,
        )
        return self._transition(state, event, effects)

    def _microphone_lease_changed(
        self,
        current: AssistantState,
        event: MicrophoneLeaseChanged,
    ) -> Transition:
        if event.generation < current.audio.microphone_lease_generation:
            return Transition.unchanged(current)
        state = replace(
            current,
            audio=replace(
                current.audio,
                microphone_owner=event.owner,
                microphone_lease_generation=event.generation,
            ),
            status_text=event.reason,
        )
        return self._transition(state, event)

    @staticmethod
    def _matches_voice_event(
        current: AssistantState,
        connection_generation: int,
        capture_generation: int,
        turn_token: int,
    ) -> bool:
        return bool(
            connection_generation == current.connection.connection_generation
            and capture_generation == current.audio.capture_generation
            and turn_token == current.conversation.active_voice_turn_token
        )

    @staticmethod
    def _matches_voice_protocol_event(
        current: AssistantState,
        generation: int,
        turn_token: int | None,
        session_id: str | None,
    ) -> bool:
        if generation != current.connection.connection_generation:
            return False
        if turn_token != current.conversation.active_voice_turn_token:
            return False
        if session_id and session_id != current.connection.session_id:
            return False
        return True

    def _enable(self, current: AssistantState, event: EnableRequested) -> Transition:
        if current.enabled:
            return self._transition(current, event)
        state = replace(
            current,
            phase=AssistantPhase.IDLE,
            enabled=True,
            connection=replace(
                current.connection,
                status=AssistantConnectionStatus.DISCONNECTED,
                session_id=None,
            ),
            audio=self._idle_audio(current.audio),
            recovery=replace(
                current.recovery,
                reconnect_attempt=0,
                next_reconnect_at_ns=None,
                manual_disconnect_requested=False,
            ),
            status_text="助手已启用，等待连接",
            error=None,
        )
        return self._transition(state, event)

    def _disable(
        self,
        current: AssistantState,
        event: DisableRequested | ShutdownRequested,
        *,
        status_text: str,
    ) -> Transition:
        old_generation = current.connection.connection_generation
        next_generation = old_generation + 1
        state = replace(
            current,
            phase=AssistantPhase.DISABLED,
            enabled=False,
            connection=ConnectionState(
                websocket_url_public=current.connection.websocket_url_public,
                connection_generation=next_generation,
                close_code=1000,
                close_reason=("shutdown" if isinstance(event, ShutdownRequested) else "disabled"),
            ),
            audio=self._idle_audio(
                current.audio,
                invalidate_capture=True,
                invalidate_playback=True,
                invalidate_wakeword=True,
                invalidate_microphone_lease=True,
            ),
            conversation=self._idle_conversation(
                current.conversation,
                invalidate_streaming=True,
            ),
            recovery=replace(
                current.recovery,
                reconnect_attempt=0,
                last_reconnect_decision=(
                    "shutdown" if isinstance(event, ShutdownRequested) else "disabled"
                ),
                next_reconnect_at_ns=None,
                manual_disconnect_requested=True,
            ),
            status_text=status_text,
            error=None,
        )
        effects = (
            CancelReconnect(),
            CancelRuntimeEffects(
                reason=("shutdown" if isinstance(event, ShutdownRequested) else "disabled")
            ),
            CloseTransport(
                generation=old_generation,
                reason=("shutdown" if isinstance(event, ShutdownRequested) else "disabled"),
            ),
        )
        return self._transition(state, event, effects)

    def _switch_runtime(
        self,
        current: AssistantState,
        event: UseFakeRuntimeRequested | UseRealRuntimeRequested,
        mode: AssistantRuntimeMode,
    ) -> Transition:
        if current.runtime_mode is mode:
            return self._transition(current, event)

        old_generation = current.connection.connection_generation
        state = replace(
            current,
            runtime_mode=mode,
            phase=AssistantPhase.IDLE if current.enabled else AssistantPhase.DISABLED,
            connection=ConnectionState(
                websocket_url_public=current.connection.websocket_url_public,
                connection_generation=old_generation + 1,
                close_reason="runtime_mode_changed",
            ),
            audio=self._idle_audio(
                current.audio,
                invalidate_capture=True,
                invalidate_playback=True,
                invalidate_wakeword=True,
                invalidate_microphone_lease=True,
            ),
            conversation=self._idle_conversation(
                current.conversation,
                invalidate_streaming=True,
            ),
            recovery=replace(
                current.recovery,
                reconnect_attempt=0,
                next_reconnect_at_ns=None,
                manual_disconnect_requested=True,
                last_reconnect_decision="runtime_mode_changed",
            ),
            status_text=(
                "已切换到 Scripted Fake Runtime"
                if mode is AssistantRuntimeMode.FAKE
                else "已切换到真实 WebSocket Runtime"
            ),
            error=None,
        )
        effects: tuple[AssistantEffect, ...] = (
            CancelReconnect(),
            CancelRuntimeEffects(reason="runtime_mode_changed"),
        )
        if current.connection.status is not AssistantConnectionStatus.DISCONNECTED:
            effects = (
                *effects,
                CloseTransport(generation=old_generation, reason="runtime_mode_changed"),
            )
        return self._transition(state, event, effects)

    def _connect(self, current: AssistantState, event: ConnectRequested) -> Transition:
        if not current.enabled:
            return self._error(
                current,
                event,
                code=AssistantErrorCode.ASSISTANT_DISABLED.value,
                message="助手未启用，不能连接",
                category=AssistantErrorCategory.VALIDATION,
                recoverable=True,
            )
        if current.connection.status is AssistantConnectionStatus.CONNECTED:
            return self._transition(replace(current, status_text="助手已经连接", error=None), event)
        if current.connection.status is AssistantConnectionStatus.CONNECTING:
            return self._transition(replace(current, status_text="助手正在连接"), event)

        old_generation = current.connection.connection_generation
        generation = old_generation + 1
        connection = ConnectionState(
            status=AssistantConnectionStatus.CONNECTING,
            websocket_url_public=(
                "scripted://fake-runtime"
                if current.runtime_mode is AssistantRuntimeMode.FAKE
                else current.connection.websocket_url_public
            ),
            connection_generation=generation,
        )
        state = replace(
            current,
            phase=AssistantPhase.CONNECTING,
            connection=connection,
            recovery=replace(
                current.recovery,
                reconnect_attempt=0,
                last_reconnect_decision="manual_connect",
                next_reconnect_at_ns=None,
                manual_disconnect_requested=False,
            ),
            status_text=(
                "正在连接 Scripted Fake Runtime"
                if current.runtime_mode is AssistantRuntimeMode.FAKE
                else "正在连接真实 WebSocket，等待 hello/session"
            ),
            error=None,
        )
        effects: list[AssistantEffect] = [CancelReconnect()]
        if (
            current.recovery.next_reconnect_at_ns is not None
            or current.phase is AssistantPhase.RECONNECTING
        ):
            effects.extend(
                (
                    CancelRuntimeEffects(reason="manual_connect"),
                    CloseTransport(generation=old_generation, reason="manual_connect"),
                )
            )
        effects.append(OpenTransport(generation=generation, runtime_mode=current.runtime_mode))
        return self._transition(state, event, tuple(effects))

    def _reconnect(self, current: AssistantState, event: ReconnectRequested) -> Transition:
        if not current.enabled:
            return self._error(
                current,
                event,
                code=AssistantErrorCode.ASSISTANT_DISABLED.value,
                message="助手未启用，不能重连",
                category=AssistantErrorCategory.VALIDATION,
                recoverable=True,
            )
        old_generation = current.connection.connection_generation
        generation = old_generation + 1
        state = replace(
            current,
            phase=AssistantPhase.RECONNECTING,
            connection=ConnectionState(
                status=AssistantConnectionStatus.CONNECTING,
                websocket_url_public=(
                    "scripted://fake-runtime"
                    if current.runtime_mode is AssistantRuntimeMode.FAKE
                    else current.connection.websocket_url_public
                ),
                connection_generation=generation,
            ),
            audio=self._idle_audio(current.audio),
            conversation=self._idle_conversation(current.conversation),
            recovery=replace(
                current.recovery,
                reconnect_attempt=0,
                last_reconnect_decision="manual_reconnect",
                next_reconnect_at_ns=None,
                manual_disconnect_requested=False,
            ),
            status_text=(
                "正在手工重连 Scripted Fake Runtime"
                if current.runtime_mode is AssistantRuntimeMode.FAKE
                else "正在手工重连真实 WebSocket"
            ),
            error=None,
        )
        effects = (
            CancelReconnect(),
            CancelRuntimeEffects(reason="manual_reconnect"),
            CloseTransport(generation=old_generation, reason="manual_reconnect"),
            OpenTransport(generation=generation, runtime_mode=current.runtime_mode),
        )
        return self._transition(state, event, effects)

    def _disconnect(self, current: AssistantState, event: DisconnectRequested) -> Transition:
        old_generation = current.connection.connection_generation
        if current.connection.status is AssistantConnectionStatus.DISCONNECTED:
            state = replace(
                current,
                phase=(AssistantPhase.IDLE if current.enabled else AssistantPhase.DISABLED),
                recovery=replace(
                    current.recovery,
                    reconnect_attempt=0,
                    next_reconnect_at_ns=None,
                    manual_disconnect_requested=True,
                    last_reconnect_decision="manual_disconnect",
                ),
                status_text="助手连接已关闭",
                error=None,
            )
            return self._transition(state, event, (CancelReconnect(),))

        state = replace(
            current,
            phase=AssistantPhase.IDLE if current.enabled else AssistantPhase.DISABLED,
            connection=replace(
                current.connection,
                status=AssistantConnectionStatus.CLOSING,
                session_id=None,
                close_reason=event.reason,
            ),
            audio=self._idle_audio(current.audio),
            conversation=self._idle_conversation(current.conversation),
            recovery=replace(
                current.recovery,
                reconnect_attempt=0,
                next_reconnect_at_ns=None,
                manual_disconnect_requested=True,
                last_reconnect_decision="manual_disconnect",
            ),
            status_text="正在断开助手连接",
            error=None,
        )
        effects = (
            CancelReconnect(),
            CancelRuntimeEffects(reason=event.reason),
            CloseTransport(generation=old_generation, reason=event.reason),
        )
        return self._transition(state, event, effects)

    def _submit_text(self, current: AssistantState, event: TextSubmitted) -> Transition:
        text = event.text.strip()
        if not text:
            return self._error(
                current,
                event,
                code=AssistantErrorCode.EMPTY_TEXT.value,
                message="文本不能为空",
                category=AssistantErrorCategory.VALIDATION,
                recoverable=True,
                preserve_phase=True,
            )
        if not current.is_connected:
            return self._error(
                current,
                event,
                code=AssistantErrorCode.ASSISTANT_NOT_CONNECTED.value,
                message="助手未连接，不能发送文本",
                category=AssistantErrorCategory.TRANSPORT,
                recoverable=True,
            )
        if current.conversation.active_text_turn_token is not None:
            return self._error(
                current,
                event,
                code=AssistantErrorCode.TEXT_TURN_IN_PROGRESS.value,
                message="上一文本回合尚未完成",
                category=AssistantErrorCategory.VALIDATION,
                recoverable=True,
                preserve_phase=True,
            )

        turn_token = current.conversation.text_turn_counter + 1
        state = replace(
            current,
            phase=AssistantPhase.THINKING,
            conversation=replace(
                current.conversation,
                active_entry_source=AssistantEntrySource.TEXT,
                last_user_text=text,
                last_assistant_text=None,
                last_assistant_source_type=None,
                assistant_reply_buffer="",
                text_turn_counter=turn_token,
                active_text_turn_token=turn_token,
                active_text_turn_started_at_ns=event.at_ns,
            ),
            status_text=f"文本回合 {turn_token} 已提交，等待助手回复",
            error=None,
        )
        return self._transition(
            state,
            event,
            (
                SendText(
                    generation=current.connection.connection_generation,
                    turn_token=turn_token,
                    text=text,
                ),
            ),
        )

    def _transport_opened(self, current: AssistantState, event: TransportOpened) -> Transition:
        if self._is_stale_connection_event(current, event.generation):
            return Transition.unchanged(current)
        if current.connection.status is not AssistantConnectionStatus.CONNECTING:
            return Transition.unchanged(current)
        state = replace(
            current,
            connection=replace(
                current.connection,
                opened_at_ns=event.at_ns,
                websocket_url_public=(
                    event.websocket_url_public or current.connection.websocket_url_public
                ),
            ),
            status_text=(
                "Fake Transport 已打开，等待 hello/session"
                if current.runtime_mode is AssistantRuntimeMode.FAKE
                else "真实 WebSocket 已打开，等待 hello/session"
            ),
        )
        return self._transition(state, event)

    def _hello_sent(self, current: AssistantState, event: ClientHelloSent) -> Transition:
        if self._is_stale_connection_event(current, event.generation):
            return Transition.unchanged(current)
        if current.connection.status is not AssistantConnectionStatus.CONNECTING:
            return Transition.unchanged(current)
        state = replace(
            current,
            connection=replace(current.connection, hello_sent_at_ns=event.at_ns),
            protocol=replace(
                current.protocol,
                last_client_json_redacted=event.raw_json_redacted,
                last_protocol_event="ClientHelloSent",
                last_protocol_error=None,
            ),
            status_text="客户端 hello 已发送，等待服务端 session",
        )
        return self._transition(state, event)

    def _hello_received(self, current: AssistantState, event: ServerHelloReceived) -> Transition:
        if self._is_stale_connection_event(current, event.generation):
            return Transition.unchanged(current)
        if current.connection.status is not AssistantConnectionStatus.CONNECTING:
            return Transition.unchanged(current)
        if event.transport and event.transport != "websocket":
            disconnected = replace(
                current,
                connection=replace(
                    current.connection,
                    status=AssistantConnectionStatus.DISCONNECTED,
                    session_id=None,
                    connection_generation=event.generation + 1,
                    hello_received_at_ns=event.at_ns,
                    close_reason="unsupported_hello_transport",
                ),
                protocol=replace(
                    current.protocol,
                    last_server_json_redacted=event.raw_json_redacted,
                    last_protocol_event="ServerHelloReceived",
                    last_protocol_error=f"unsupported transport: {event.transport}",
                ),
            )
            return self._error(
                disconnected,
                event,
                code="hello_unsupported_transport",
                message=f"服务端 hello transport 不兼容：{event.transport}",
                category=AssistantErrorCategory.PROTOCOL,
                recoverable=True,
                effects=(
                    CloseTransport(
                        generation=event.generation,
                        reason="hello_unsupported_transport",
                    ),
                ),
            )

        session_id = event.session_id.strip()
        if not session_id:
            disconnected = replace(
                current,
                connection=replace(
                    current.connection,
                    status=AssistantConnectionStatus.DISCONNECTED,
                    session_id=None,
                    connection_generation=event.generation + 1,
                    hello_received_at_ns=event.at_ns,
                    close_reason="empty_session_id",
                ),
                protocol=replace(
                    current.protocol,
                    last_server_json_redacted=event.raw_json_redacted,
                    last_protocol_event="ServerHelloReceived",
                    last_protocol_error="missing session_id",
                ),
            )
            return self._error(
                disconnected,
                event,
                code="hello_missing_session_id",
                message="服务端 hello 未返回非空 session_id",
                category=AssistantErrorCategory.PROTOCOL,
                recoverable=True,
                effects=(
                    CloseTransport(
                        generation=event.generation,
                        reason="hello_missing_session_id",
                    ),
                ),
            )

        recovering_streaming = (
            current.conversation.streaming_session_active
            and current.conversation.streaming_state is StreamingConversationState.RECOVERING
            and current.conversation.preferred_voice_mode
            is VoiceInteractionMode.STREAMING_CONVERSATION
        )
        conversation = current.conversation
        audio = current.audio
        effects: tuple[AssistantEffect, ...] = (CancelReconnect(),)
        status_text = (
            "Scripted Fake Runtime 已连接"
            if current.runtime_mode is AssistantRuntimeMode.FAKE
            else "真实 WebSocket hello/session 已验证"
        )
        if recovering_streaming:
            capture_generation = current.audio.capture_generation + 1
            turn_token = current.conversation.voice_turn_counter + 1
            turn_index = current.conversation.streaming_turn_index + 1
            audio = replace(
                current.audio,
                capture_generation=capture_generation,
                status=AssistantAudioStatus.IDLE,
                microphone_owner=MicrophoneOwner.NONE,
                active_capture_mode=None,
                captured_frames=0,
                encoded_frames=0,
                uploaded_frames=0,
                dropped_pcm_frames=0,
                uplink_overflow_count=0,
            )
            conversation = replace(
                current.conversation,
                active_entry_source=AssistantEntrySource.STREAMING_BUTTON,
                voice_turn_counter=turn_token,
                active_voice_turn_token=turn_token,
                active_voice_turn_started_at_ns=event.at_ns,
                pending_voice_turn_completion_token=None,
                streaming_state=StreamingConversationState.STARTING,
                streaming_turn_index=turn_index,
                active_streaming_turn_token=turn_token,
                streaming_response_deadline_ns=None,
                vad_state=VoiceActivityState.WARMUP,
                vad_status_text="VAD 准备中",
            )
            effects = (
                CancelReconnect(),
                StartStreamingConversation(
                    connection_generation=event.generation,
                    streaming_generation=current.conversation.streaming_generation,
                    capture_generation=capture_generation,
                    turn_token=turn_token,
                    turn_index=turn_index,
                    requested_at_ns=event.at_ns,
                    idle_timeout_ms=current.conversation.streaming_idle_timeout_ms,
                    source=AssistantEntrySource.STREAMING_BUTTON,
                    session_id=current.conversation.streaming_session_id,
                ),
            )
            status_text = "连接已恢复，正在恢复连续对话监听"

        state = replace(
            current,
            phase=AssistantPhase.CONNECTED,
            connection=replace(
                current.connection,
                status=AssistantConnectionStatus.CONNECTED,
                session_id=session_id,
                hello_received_at_ns=event.at_ns,
                close_code=None,
                close_reason=None,
            ),
            activation=replace(current.activation, status=AssistantActivationStatus.ACTIVATED),
            audio=audio,
            conversation=conversation,
            protocol=replace(
                current.protocol,
                last_server_json_redacted=event.raw_json_redacted,
                last_protocol_event="ServerHelloReceived",
                last_protocol_error=None,
            ),
            diagnostics=replace(
                current.diagnostics,
                gate_real_handshake_verified=(
                    current.diagnostics.gate_real_handshake_verified
                    or current.runtime_mode is AssistantRuntimeMode.REAL
                ),
            ),
            recovery=replace(
                current.recovery,
                reconnect_attempt=0,
                last_reconnect_decision="connected",
                next_reconnect_at_ns=None,
                manual_disconnect_requested=False,
            ),
            status_text=status_text,
            error=None,
        )
        return self._transition(state, event, effects)

    def _client_text_sent(
        self,
        current: AssistantState,
        event: ClientTextSent,
    ) -> Transition:
        if self._is_stale_connection_event(current, event.generation):
            return Transition.unchanged(current)
        if event.turn_token != current.conversation.active_text_turn_token:
            return Transition.unchanged(current)
        state = replace(
            current,
            protocol=replace(
                current.protocol,
                last_client_json_redacted=event.raw_json_redacted,
                last_protocol_event=f"ClientTextSent:{event.turn_token}",
                last_protocol_error=None,
            ),
            status_text=f"文本回合 {event.turn_token} 已写入 WebSocket",
            error=None,
        )
        return self._transition(state, event)

    def _assistant_text(
        self,
        current: AssistantState,
        event: AssistantTextReceived,
    ) -> Transition:
        if self._is_stale_connection_event(current, event.generation):
            return Transition.unchanged(current)
        if not current.is_connected:
            return Transition.unchanged(current)
        if not self._matches_active_text_turn(
            current,
            turn_token=event.turn_token,
            session_id=event.session_id,
        ):
            return self._archive_late_text_event(
                current,
                event,
                event_name=f"LateAssistantText:{event.source_type}",
                raw_json_redacted=event.raw_json_redacted,
            )

        source_type = event.source_type.strip().lower() or "text"
        cleaned_text = event.text.strip()
        protocol = replace(
            current.protocol,
            last_server_json_redacted=event.raw_json_redacted,
            last_protocol_event=f"AssistantTextReceived:{source_type}",
            last_protocol_error=None,
        )
        if source_type == "stt":
            state = replace(
                current,
                conversation=replace(
                    current.conversation,
                    last_stt_text=cleaned_text or None,
                ),
                protocol=protocol,
                status_text="收到 STT 文本；文本输入回合不覆盖已提交的用户文本",
                error=None,
            )
            return self._transition(state, event)

        if source_type == "llm" and not has_readable_transcript_text(cleaned_text):
            state = replace(
                current,
                protocol=protocol,
                status_text="收到 LLM 情绪/状态标记，未写入产品 transcript",
                error=None,
            )
            return self._transition(state, event)

        if not has_readable_transcript_text(cleaned_text):
            state = replace(
                current,
                protocol=protocol,
                status_text=f"收到空白 {source_type} 文本，未写入产品 transcript",
                error=None,
            )
            return self._transition(state, event)

        merged = merge_assistant_transcript(
            current.conversation.assistant_reply_buffer,
            cleaned_text,
        )
        state = replace(
            current,
            phase=AssistantPhase.CONNECTED,
            conversation=replace(
                current.conversation,
                last_assistant_text=merged,
                last_assistant_source_type=source_type,
                assistant_reply_buffer=merged,
                active_entry_source=AssistantEntrySource.TEXT,
            ),
            protocol=protocol,
            diagnostics=replace(
                current.diagnostics,
                gate_real_text_verified=(
                    current.diagnostics.gate_real_text_verified
                    or current.runtime_mode is AssistantRuntimeMode.REAL
                ),
            ),
            status_text=f"收到助手 {source_type} 文本回复",
            error=None,
        )
        return self._transition(state, event)

    def _tts_state(
        self,
        current: AssistantState,
        event: TtsStateReceived,
    ) -> Transition:
        if self._is_stale_connection_event(current, event.generation):
            return Transition.unchanged(current)
        if not current.is_connected:
            return Transition.unchanged(current)
        if not self._matches_active_text_turn(
            current,
            turn_token=event.turn_token,
            session_id=event.session_id,
        ):
            return self._archive_late_text_event(
                current,
                event,
                event_name=f"LateTtsState:{event.state}",
                raw_json_redacted=event.raw_json_redacted,
            )

        protocol = replace(
            current.protocol,
            last_server_json_redacted=event.raw_json_redacted,
            last_protocol_event=f"TtsStateReceived:{event.state}",
            last_protocol_error=None,
        )
        spoken_text = (event.text or "").strip()
        if not has_readable_transcript_text(spoken_text):
            state = replace(
                current,
                protocol=protocol,
                status_text=f"收到 TTS state={event.state}；Gate 4 前仅记录状态",
                error=None,
            )
            return self._transition(state, event)

        merged = merge_assistant_transcript(
            current.conversation.assistant_reply_buffer,
            spoken_text,
        )
        state = replace(
            current,
            phase=AssistantPhase.CONNECTED,
            conversation=replace(
                current.conversation,
                last_assistant_text=merged,
                last_assistant_source_type="tts",
                assistant_reply_buffer=merged,
                active_entry_source=AssistantEntrySource.TEXT,
            ),
            protocol=protocol,
            diagnostics=replace(
                current.diagnostics,
                gate_real_text_verified=(
                    current.diagnostics.gate_real_text_verified
                    or current.runtime_mode is AssistantRuntimeMode.REAL
                ),
            ),
            status_text=f"收到 TTS 文本 state={event.state}；Gate 4 前不播放",
            error=None,
        )
        return self._transition(state, event)

    def _text_turn_completed(
        self,
        current: AssistantState,
        event: TextTurnCompleted,
    ) -> Transition:
        if self._is_stale_connection_event(current, event.generation):
            return Transition.unchanged(current)
        if event.turn_token != current.conversation.active_text_turn_token:
            return Transition.unchanged(current)

        state = replace(
            current,
            phase=AssistantPhase.CONNECTED if current.is_connected else current.phase,
            conversation=replace(
                current.conversation,
                active_text_turn_token=None,
                active_text_turn_started_at_ns=None,
                last_completed_text_turn_token=event.turn_token,
                last_text_turn_completed_at_ns=event.at_ns,
            ),
            status_text=(
                f"文本回合 {event.turn_token} 完成"
                if event.had_assistant_text
                else f"文本回合 {event.turn_token} 结束，但没有可显示的助手文本"
            ),
            error=None,
        )
        return self._transition(state, event)

    @staticmethod
    def _matches_active_text_turn(
        current: AssistantState,
        *,
        turn_token: int | None,
        session_id: str | None,
    ) -> bool:
        active_token = current.conversation.active_text_turn_token
        if active_token is None or turn_token != active_token:
            return False
        if session_id and session_id != current.connection.session_id:
            return False
        return True

    def _archive_late_text_event(
        self,
        current: AssistantState,
        event: AssistantTextReceived | TtsStateReceived,
        *,
        event_name: str,
        raw_json_redacted: str | None,
    ) -> Transition:
        state = replace(
            current,
            conversation=replace(
                current.conversation,
                late_text_event_count=current.conversation.late_text_event_count + 1,
            ),
            protocol=replace(
                current.protocol,
                last_server_json_redacted=raw_json_redacted,
                last_protocol_event=event_name,
                last_protocol_error=None,
            ),
            status_text="已归档不属于当前文本回合的迟到协议文本",
        )
        return self._transition(state, event)

    def _protocol_observed(
        self,
        current: AssistantState,
        event: ProtocolMessageObserved,
    ) -> Transition:
        if self._is_stale_connection_event(current, event.generation):
            return Transition.unchanged(current)
        state = replace(
            current,
            protocol=replace(
                current.protocol,
                last_server_json_redacted=event.raw_json_redacted,
                last_protocol_event=event.event_name,
                last_protocol_error=None,
            ),
            status_text=f"收到协议事件：{event.message_type}",
        )
        return self._transition(state, event)

    def _token_usage_received(
        self,
        current: AssistantState,
        event: TokenUsageReceived,
    ) -> Transition:
        if self._is_stale_connection_event(current, event.generation):
            return Transition.unchanged(current)
        if event.session_id and event.session_id != current.connection.session_id:
            return Transition.unchanged(current)
        token_usage = TokenUsageState(
            observed=True,
            turn_id=event.turn_id,
            model=event.model,
            api_call_count=event.api_call_count,
            llm_calls_started=event.llm_calls_started,
            tool_call_count=event.tool_call_count,
            tool_followup_count=event.tool_followup_count,
            input_tokens=event.input_tokens,
            output_tokens=event.output_tokens,
            total_tokens=event.total_tokens,
            known_total_tokens=event.known_total_tokens,
            provider_usage_complete=event.provider_usage_complete,
            duration_ms=event.duration_ms,
            status=event.status,
            budget_enabled=event.budget_enabled,
            budget_status=event.budget_status,
            budget_reason=event.budget_reason,
            max_total_tokens_per_turn=event.max_total_tokens_per_turn,
            max_llm_calls_per_turn=event.max_llm_calls_per_turn,
            max_tool_calls_per_turn=event.max_tool_calls_per_turn,
            max_output_tokens_per_request=event.max_output_tokens_per_request,
            warn_at_percent=event.warn_at_percent,
            output_cap_enforced=event.output_cap_enforced,
            budget_profile=event.budget_profile,
            request_route=event.request_route,
            routing_reason=event.routing_reason,
            available_tool_count=event.available_tool_count,
            selected_tool_count=event.selected_tool_count,
            selected_tool_schema_chars=event.selected_tool_schema_chars,
            max_tools_per_request=event.max_tools_per_request,
            max_tool_schema_chars_per_request=(
                event.max_tool_schema_chars_per_request
            ),
            max_message_chars_per_request=event.max_message_chars_per_request,
        )
        state = replace(
            current,
            token_usage=token_usage,
            protocol=replace(
                current.protocol,
                last_server_json_redacted=event.raw_json_redacted,
                last_protocol_event="TokenUsageReceived",
                last_protocol_error=None,
            ),
            status_text=(
                f"Token：{event.known_total_tokens}/"
                f"{event.max_total_tokens_per_turn or '-'} · "
                f"{event.budget_status}"
            ),
        )
        return self._transition(state, event)

    def _protocol_unknown(
        self,
        current: AssistantState,
        event: ProtocolUnknownMessageReceived,
    ) -> Transition:
        if self._is_stale_connection_event(current, event.generation):
            return Transition.unchanged(current)
        state = replace(
            current,
            protocol=replace(
                current.protocol,
                last_server_json_redacted=event.raw_json_redacted,
                last_protocol_event="UnknownJson",
                last_unknown_message_type=event.message_type,
                last_protocol_error=None,
            ),
            status_text=f"已忽略未知协议消息：{event.message_type}",
        )
        return self._transition(state, event)

    def _protocol_invalid(
        self,
        current: AssistantState,
        event: ProtocolInvalidMessageReceived,
    ) -> Transition:
        if self._is_stale_connection_event(current, event.generation):
            return Transition.unchanged(current)
        state = replace(
            current,
            protocol=replace(
                current.protocol,
                last_server_json_redacted=event.raw_text_redacted,
                last_protocol_event="ProtocolError",
                last_protocol_error=event.error,
            ),
            status_text="收到无效协议消息，连接保持运行",
        )
        return self._transition(state, event)

    def _binary_audio(
        self,
        current: AssistantState,
        event: BinaryAudioReceived,
    ) -> Transition:
        if self._is_stale_connection_event(current, event.generation):
            return Transition.unchanged(current)
        state = replace(
            current,
            protocol=replace(
                current.protocol,
                last_protocol_event="BinaryAudio",
                last_binary_size_bytes=event.size_bytes,
            ),
            status_text=f"收到二进制下行帧：{event.size_bytes} bytes（Gate 4 前不播放）",
        )
        return self._transition(state, event)

    def _transport_closed(self, current: AssistantState, event: TransportClosed) -> Transition:
        if self._is_stale_connection_event(current, event.generation):
            return Transition.unchanged(current)

        # One generation owns at most one recovery decision. Duplicate close/failure
        # callbacks (including cleanup closes) must not advance the retry counter or
        # replace the already-owned reconnect timer.
        if current.recovery.next_reconnect_at_ns is not None:
            return Transition.unchanged(current)

        connection = replace(
            current.connection,
            status=AssistantConnectionStatus.DISCONNECTED,
            session_id=None,
            close_code=event.code,
            close_reason=event.reason,
        )
        decision = self._reconnect_policy.decide_close(
            close_code=event.code,
            reason=event.reason,
            assistant_enabled=current.enabled,
            manual_disconnect_requested=(
                current.recovery.manual_disconnect_requested or event.expected
            ),
            current_attempt=current.recovery.reconnect_attempt,
            generation=event.generation,
            jitter_seed=event.at_ns,
        )
        if not decision.should_reconnect:
            return self._no_recovery_after_transport_event(
                current,
                event,
                connection=connection,
                decision=decision,
            )
        return self._schedule_recovery(
            current,
            event,
            connection=connection,
            decision=decision,
            error_code=AssistantErrorCode.TRANSPORT_CLOSED_ABNORMALLY.value,
            error_message=f"助手连接异常关闭：{event.reason}",
            error_details=f"close_code={event.code}",
            cleanup_reason="transport_closed_abnormally",
        )

    def _transport_failed(self, current: AssistantState, event: TransportFailed) -> Transition:
        if self._is_stale_connection_event(current, event.generation):
            return Transition.unchanged(current)
        if current.recovery.next_reconnect_at_ns is not None:
            return Transition.unchanged(current)
        connection = replace(
            current.connection,
            status=AssistantConnectionStatus.DISCONNECTED,
            session_id=None,
            close_reason=event.message,
        )
        if not event.retryable:
            disconnected = replace(
                current,
                connection=connection,
                audio=self._idle_audio(current.audio),
                conversation=self._idle_conversation(current.conversation),
                recovery=replace(
                    current.recovery,
                    last_reconnect_decision="non_retryable_failure",
                    next_reconnect_at_ns=None,
                ),
            )
            return self._error(
                disconnected,
                event,
                code=AssistantErrorCode.TRANSPORT_FAILURE.value,
                message=event.message,
                category=AssistantErrorCategory.TRANSPORT,
                recoverable=True,
            )
        decision = self._reconnect_policy.decide_failure(
            assistant_enabled=current.enabled,
            manual_disconnect_requested=current.recovery.manual_disconnect_requested,
            current_attempt=current.recovery.reconnect_attempt,
            generation=event.generation,
            jitter_seed=event.at_ns,
        )
        if not decision.should_reconnect:
            return self._no_recovery_after_transport_event(
                current,
                event,
                connection=connection,
                decision=decision,
                failure_message=event.message,
            )
        return self._schedule_recovery(
            current,
            event,
            connection=connection,
            decision=decision,
            error_code=AssistantErrorCode.TRANSPORT_FAILURE.value,
            error_message=event.message,
            error_details=None,
            cleanup_reason="transport_failure",
        )

    def _reconnect_timer_fired(
        self,
        current: AssistantState,
        event: ReconnectTimerFired,
    ) -> Transition:
        if not current.enabled or current.recovery.manual_disconnect_requested:
            return Transition.unchanged(current)
        if self._is_stale_connection_event(current, event.generation):
            return Transition.unchanged(current)
        if event.attempt != current.recovery.reconnect_attempt:
            return Transition.unchanged(current)
        if current.recovery.next_reconnect_at_ns is None:
            return Transition.unchanged(current)

        old_generation = current.connection.connection_generation
        generation = old_generation + 1
        state = replace(
            current,
            phase=AssistantPhase.RECONNECTING,
            connection=ConnectionState(
                status=AssistantConnectionStatus.CONNECTING,
                websocket_url_public=(
                    "scripted://fake-runtime"
                    if current.runtime_mode is AssistantRuntimeMode.FAKE
                    else current.connection.websocket_url_public
                ),
                connection_generation=generation,
            ),
            recovery=replace(
                current.recovery,
                last_reconnect_decision=f"auto_reconnect_open_attempt_{event.attempt}",
                next_reconnect_at_ns=None,
                manual_disconnect_requested=False,
            ),
            status_text=f"正在执行第 {event.attempt} 次自动重连",
            error=None,
        )
        return self._transition(
            state,
            event,
            (
                CancelReconnect(),
                CloseTransport(generation=old_generation, reason="auto_reconnect"),
                OpenTransport(generation=generation, runtime_mode=current.runtime_mode),
            ),
        )

    def _schedule_recovery(
        self,
        current: AssistantState,
        event: TransportClosed | TransportFailed,
        *,
        connection: ConnectionState,
        decision: ReconnectDecision,
        error_code: str,
        error_message: str,
        error_details: str | None,
        cleanup_reason: str,
    ) -> Transition:
        assert decision.delay_seconds is not None
        next_reconnect_at_ns = event.at_ns + int(decision.delay_seconds * 1_000_000_000)
        streaming_active = current.conversation.streaming_session_active
        if streaming_active:
            conversation = replace(
                current.conversation,
                active_voice_turn_token=None,
                active_voice_turn_started_at_ns=None,
                pending_voice_turn_completion_token=None,
                active_streaming_turn_token=None,
                streaming_state=StreamingConversationState.RECOVERING,
                streaming_response_deadline_ns=None,
                vad_state=VoiceActivityState.DISABLED,
                vad_status_text="网络恢复中",
            )
        else:
            conversation = self._idle_conversation(current.conversation)
        state = replace(
            current,
            phase=AssistantPhase.RECONNECTING,
            connection=connection,
            audio=self._idle_audio(
                current.audio,
                invalidate_capture=streaming_active,
                invalidate_microphone_lease=streaming_active,
            ),
            conversation=conversation,
            recovery=replace(
                current.recovery,
                reconnect_attempt=decision.next_attempt,
                last_reconnect_decision=decision.decision_label,
                next_reconnect_at_ns=next_reconnect_at_ns,
                manual_disconnect_requested=False,
                runtime_error_count=current.recovery.runtime_error_count + 1,
            ),
            status_text=(
                "连续对话连接中断，正在恢复" if streaming_active else decision.user_message
            ),
            error=AssistantError(
                code=error_code,
                message=error_message,
                category=AssistantErrorCategory.TRANSPORT,
                recoverable=True,
                source_event=type(event).__name__,
                occurred_at_ns=event.at_ns,
                details_redacted=error_details,
            ),
        )
        return self._transition(
            state,
            event,
            (
                CancelRuntimeEffects(reason=cleanup_reason),
                CloseTransport(generation=event.generation, reason=cleanup_reason),
                ScheduleReconnect(
                    attempt=decision.next_attempt,
                    delay_seconds=decision.delay_seconds,
                    generation=event.generation,
                ),
            ),
        )

    def _no_recovery_after_transport_event(
        self,
        current: AssistantState,
        event: TransportClosed | TransportFailed,
        *,
        connection: ConnectionState,
        decision: ReconnectDecision,
        failure_message: str | None = None,
    ) -> Transition:
        exhausted = "max_attempts_reached" in decision.decision_label
        error = None
        phase = AssistantPhase.IDLE if current.enabled else AssistantPhase.DISABLED
        if exhausted:
            phase = AssistantPhase.ERROR
            error = AssistantError(
                code=AssistantErrorCode.RECONNECT_EXHAUSTED.value,
                message=failure_message or decision.user_message,
                category=AssistantErrorCategory.TRANSPORT,
                recoverable=True,
                source_event=type(event).__name__,
                occurred_at_ns=event.at_ns,
            )
        state = replace(
            current,
            phase=phase,
            connection=connection,
            audio=self._idle_audio(current.audio),
            conversation=self._idle_conversation(current.conversation),
            recovery=replace(
                current.recovery,
                reconnect_attempt=(current.recovery.reconnect_attempt if exhausted else 0),
                last_reconnect_decision=decision.decision_label,
                next_reconnect_at_ns=None,
                runtime_error_count=(
                    current.recovery.runtime_error_count + 1
                    if exhausted
                    else current.recovery.runtime_error_count
                ),
            ),
            status_text=decision.user_message,
            error=error,
        )
        return self._transition(state, event, (CancelReconnect(),))

    def _ensure_identity(
        self,
        current: AssistantState,
        event: EnsureIdentityRequested,
    ) -> Transition:
        state = replace(
            current,
            status_text="正在准备设备身份",
            error=None,
        )
        return self._transition(state, event, (EnsureIdentity(),))

    def _reset_identity(
        self,
        current: AssistantState,
        event: ResetIdentityRequested,
    ) -> Transition:
        old_generation = current.connection.connection_generation
        next_connection = ConnectionState(
            websocket_url_public=None,
            connection_generation=old_generation + 1,
            close_code=1000,
            close_reason="identity_reset",
        )
        state = replace(
            current,
            phase=AssistantPhase.IDLE if current.enabled else AssistantPhase.DISABLED,
            connection=next_connection,
            identity=IdentityPublicState(
                identity_generation=current.identity.identity_generation + 1
            ),
            activation=ActivationState(),
            status_text="正在重置设备身份并清除身份绑定凭据",
            error=None,
        )
        effects: list[AssistantEffect] = [
            CancelReconnect(),
            CancelRuntimeEffects(reason="identity_reset"),
        ]
        if current.connection.status is not AssistantConnectionStatus.DISCONNECTED:
            effects.append(CloseTransport(generation=old_generation, reason="identity_reset"))
        effects.append(ResetIdentity())
        return self._transition(state, event, tuple(effects))

    def _identity_ready(
        self,
        current: AssistantState,
        event: IdentityReady,
    ) -> Transition:
        state = replace(
            current,
            identity=IdentityPublicState(
                device_id_masked=event.device_id_masked,
                client_id_masked=event.client_id_masked,
                identity_ready=True,
                identity_generation=event.identity_generation,
            ),
            status_text="设备身份已就绪",
            error=None,
        )
        return self._transition(state, event)

    def _identity_reset(
        self,
        current: AssistantState,
        event: IdentityReset,
    ) -> Transition:
        state = replace(
            current,
            identity=IdentityPublicState(identity_generation=event.identity_generation),
            activation=ActivationState(),
            status_text="旧设备身份及身份绑定凭据已清除",
            error=None,
        )
        return self._transition(state, event)

    def _request_activation(
        self,
        current: AssistantState,
        event: FakeActivationRequested | RealActivationRequested,
        *,
        fake: bool,
    ) -> Transition:
        expected_mode = AssistantRuntimeMode.FAKE if fake else AssistantRuntimeMode.REAL
        if current.activation.status is AssistantActivationStatus.ACTIVATING:
            return self._transition(
                replace(current, status_text="Assistant Activation 已在进行中"),
                event,
            )
        if current.runtime_mode is not expected_mode:
            return self._error(
                current,
                event,
                code="activation_runtime_mode_mismatch",
                message=(
                    "执行 Fake Activation 前必须切换到 Fake Runtime"
                    if fake
                    else "执行真实 Activation 前必须切换到 Real Runtime"
                ),
                category=AssistantErrorCategory.VALIDATION,
                recoverable=True,
            )
        state = replace(
            current,
            phase=(AssistantPhase.ACTIVATING if current.enabled else AssistantPhase.DISABLED),
            activation=replace(
                current.activation,
                status=AssistantActivationStatus.ACTIVATING,
                message=("Fake Activation 进行中" if fake else "真实 OTA/Activation 进行中"),
                last_attempt_at_ns=event.at_ns,
            ),
            status_text=("正在执行 Fake Activation" if fake else "正在执行真实 OTA/Activation"),
            error=None,
        )
        return self._transition(state, event, (RunActivation(fake=fake),))

    def _activation_started(
        self,
        current: AssistantState,
        event: ActivationStarted,
    ) -> Transition:
        state = replace(
            current,
            phase=(AssistantPhase.ACTIVATING if current.enabled else AssistantPhase.DISABLED),
            activation=replace(
                current.activation,
                status=AssistantActivationStatus.ACTIVATING,
                last_attempt_at_ns=event.at_ns,
            ),
            status_text="Assistant Activation 已开始",
            error=None,
        )
        return self._transition(state, event)

    def _activation_required(
        self,
        current: AssistantState,
        event: ActivationRequired,
    ) -> Transition:
        connection = replace(
            current.connection,
            websocket_url_public=(
                event.websocket_url_public or current.connection.websocket_url_public
            ),
        )
        protocol = replace(
            current.protocol,
            last_server_json_redacted=(
                event.diagnostics_json_redacted or current.protocol.last_server_json_redacted
            ),
            last_protocol_event="ActivationRequired",
        )
        state = replace(
            current,
            phase=AssistantPhase.IDLE if current.enabled else AssistantPhase.DISABLED,
            connection=connection,
            activation=replace(
                current.activation,
                status=AssistantActivationStatus.REQUIRED,
                activation_code=event.activation_code,
                authorization_url=event.authorization_url,
                message=event.message,
                last_attempt_at_ns=event.at_ns,
            ),
            protocol=protocol,
            status_text=event.message,
            error=None,
        )
        return self._transition(state, event)

    def _activation_succeeded(
        self,
        current: AssistantState,
        event: ActivationSucceeded,
    ) -> Transition:
        connection = replace(
            current.connection,
            websocket_url_public=event.websocket_url_public,
        )
        protocol = replace(
            current.protocol,
            last_server_json_redacted=(
                event.diagnostics_json_redacted or current.protocol.last_server_json_redacted
            ),
            last_protocol_event="ActivationSucceeded",
        )
        state = replace(
            current,
            phase=AssistantPhase.IDLE if current.enabled else AssistantPhase.DISABLED,
            connection=connection,
            activation=ActivationState(
                status=AssistantActivationStatus.ACTIVATED,
                message=event.message,
                last_attempt_at_ns=event.at_ns,
            ),
            protocol=protocol,
            status_text=event.message,
            error=None,
        )
        return self._transition(state, event)

    def _activation_failed(
        self,
        current: AssistantState,
        event: ActivationFailed,
    ) -> Transition:
        error = AssistantError(
            code="activation_failed",
            message=event.message,
            category=AssistantErrorCategory.ACTIVATION,
            recoverable=True,
            source_event=type(event).__name__,
            occurred_at_ns=event.at_ns,
            details_redacted=event.diagnostics_json_redacted,
        )
        state = replace(
            current,
            phase=AssistantPhase.ERROR if current.enabled else AssistantPhase.DISABLED,
            activation=replace(
                current.activation,
                status=AssistantActivationStatus.FAILED,
                message=event.message,
                last_attempt_at_ns=event.at_ns,
            ),
            protocol=replace(
                current.protocol,
                last_protocol_event="ActivationFailed",
                last_protocol_error=event.message,
            ),
            recovery=replace(
                current.recovery,
                runtime_error_count=current.recovery.runtime_error_count + 1,
            ),
            status_text="Assistant Activation 失败",
            error=error,
        )
        return self._transition(state, event)

    def _blocked_tool_call(
        self,
        current: AssistantState,
        event: IncomingToolCallSimulationRequested,
    ) -> Transition:
        state = replace(
            current,
            mcp=replace(
                current.mcp,
                last_tool_name=event.tool_name,
                last_tool_status="blocked_not_ready",
                last_request_id="simulated-gate2.1",
            ),
            status_text=f"MCP 工具 {event.tool_name} 已 fail-closed：Gate 5 前不执行便签修改",
            error=None,
        )
        return self._transition(state, event)

    def _tools_list_not_ready(
        self,
        current: AssistantState,
        event: ToolsListSimulationRequested,
    ) -> Transition:
        state = replace(
            current,
            mcp=replace(current.mcp, last_tool_status="tools_list_not_ready"),
            status_text="MCP tools/list 契约已保留，将在 Gate 2.3/5 接通",
            error=None,
        )
        return self._transition(state, event)

    def _audio_failure(
        self,
        current: AssistantState,
        event: AudioFailureSimulationRequested,
    ) -> Transition:
        state = (
            replace(current, audio=replace(current.audio, status=AssistantAudioStatus.ERROR))
            if current.enabled
            else current
        )
        return self._error(
            state,
            event,
            code="simulated_audio_failure",
            message=event.message,
            category=AssistantErrorCategory.AUDIO,
            recoverable=True,
        )

    def _effect_failed(
        self,
        current: AssistantState,
        event: EffectExecutionFailed,
    ) -> Transition:
        if event.generation is not None and self._is_stale_connection_event(
            current,
            event.generation,
        ):
            return Transition.unchanged(current)
        if event.effect_name in {"SetVoiceInteractionMode", "SetStreamingBargeIn"}:
            error = AssistantError(
                code="assistant_preferences_write_failed",
                message=f"设置已生效，但保存失败：{event.message}",
                category=AssistantErrorCategory.VALIDATION,
                recoverable=True,
                source_event=type(event).__name__,
                occurred_at_ns=event.at_ns,
                details_redacted=event.effect_name,
            )
            state = replace(
                current,
                recovery=replace(
                    current.recovery,
                    runtime_error_count=current.recovery.runtime_error_count + 1,
                ),
                status_text="设置已生效，但本地偏好保存失败",
                error=error,
            )
            return self._transition(state, event)
        if event.effect_name == "OpenTransport" and event.generation is not None:
            return self._transport_failed(
                current,
                TransportFailed(
                    at_ns=event.at_ns,
                    generation=event.generation,
                    message=event.message,
                ),
            )
        state = current
        if event.effect_name == "SendText":
            state = replace(
                current,
                conversation=replace(
                    current.conversation,
                    active_text_turn_token=None,
                    active_text_turn_started_at_ns=None,
                    assistant_reply_buffer="",
                ),
            )
        return self._error(
            state,
            event,
            code=AssistantErrorCode.EFFECT_EXECUTION_FAILED.value,
            message=f"{event.effect_name} 执行失败：{event.message}",
            category=AssistantErrorCategory.RUNTIME,
            recoverable=True,
        )

    def _not_ready(
        self,
        current: AssistantState,
        event: AssistantEvent,
        capability: AssistantCapability,
    ) -> Transition:
        capability_state = next(item for item in current.capabilities if item.name is capability)
        return self._error(
            current,
            event,
            code="capability_not_ready",
            message=(
                f"能力 {capability.value} 已冻结但尚未接通；"
                f"目标阶段 Gate {capability_state.target_gate}"
            ),
            category=AssistantErrorCategory.CAPABILITY,
            recoverable=True,
            details=capability_state.detail,
        )

    def _error(
        self,
        current: AssistantState,
        event: AssistantEvent,
        *,
        code: str,
        message: str,
        category: AssistantErrorCategory,
        recoverable: bool,
        details: str | None = None,
        effects: tuple[AssistantEffect, ...] = (),
        preserve_phase: bool = False,
    ) -> Transition:
        error = AssistantError(
            code=code,
            message=message,
            category=category,
            recoverable=recoverable,
            source_event=type(event).__name__,
            occurred_at_ns=event.at_ns,
            details_redacted=details,
        )
        state = replace(
            current,
            phase=(
                current.phase
                if preserve_phase
                else (AssistantPhase.ERROR if current.enabled else AssistantPhase.DISABLED)
            ),
            recovery=replace(
                current.recovery,
                runtime_error_count=current.recovery.runtime_error_count + 1,
            ),
            status_text="助手运行时错误",
            error=error,
        )
        return self._transition(state, event, effects)

    def _transition(
        self,
        state: AssistantState,
        event: AssistantEvent,
        effects: tuple[AssistantEffect, ...] = (),
    ) -> Transition:
        diagnostics = replace(
            state.diagnostics,
            last_event_name=type(event).__name__,
            last_event_at_ns=event.at_ns,
            metrics_sample_count=state.diagnostics.metrics_sample_count + 1,
        )
        next_state = replace(
            state,
            diagnostics=diagnostics,
            last_event_at_ns=event.at_ns,
        )
        return Transition(state=next_state, effects=effects).validated()

    @staticmethod
    def _is_stale_connection_event(current: AssistantState, generation: int) -> bool:
        return generation != current.connection.connection_generation

    @staticmethod
    def _idle_audio(
        audio: AudioState,
        *,
        invalidate_capture: bool = False,
        invalidate_playback: bool = False,
        invalidate_wakeword: bool = False,
        invalidate_microphone_lease: bool = False,
    ) -> AudioState:
        return replace(
            audio,
            status=AssistantAudioStatus.IDLE,
            capture_generation=audio.capture_generation + int(invalidate_capture),
            playback_generation=audio.playback_generation + int(invalidate_playback),
            wakeword_generation=audio.wakeword_generation + int(invalidate_wakeword),
            microphone_lease_generation=(
                audio.microphone_lease_generation + int(invalidate_microphone_lease)
            ),
            microphone_owner=MicrophoneOwner.NONE,
            captured_frames=0,
            encoded_frames=0,
            uploaded_frames=0,
            decoded_frames=0,
            played_frames=0,
            dropped_pcm_frames=0,
            uplink_overflow_count=0,
            push_to_talk_stop_latency_ms=None,
            first_pcm_latency_ms=None,
            first_opus_latency_ms=None,
            first_opus_upload_latency_ms=None,
            stop_listen_latency_ms=None,
            input_device_public_name=None,
            active_capture_mode=None,
            last_audio_summary=None,
        )

    @staticmethod
    def _idle_conversation(
        conversation: ConversationState,
        *,
        invalidate_streaming: bool = False,
    ) -> ConversationState:
        return replace(
            conversation,
            active_entry_source=None,
            active_text_turn_token=None,
            active_text_turn_started_at_ns=None,
            active_voice_turn_token=None,
            active_voice_turn_started_at_ns=None,
            pending_voice_turn_completion_token=None,
            assistant_reply_buffer="",
            streaming_state=StreamingConversationState.INACTIVE,
            streaming_session_active=False,
            streaming_generation=(conversation.streaming_generation + int(invalidate_streaming)),
            streaming_session_id=None,
            streaming_turn_index=0,
            active_streaming_turn_token=None,
            streaming_response_deadline_ns=None,
            barge_in_monitor_active=False,
            vad_state=VoiceActivityState.DISABLED,
            vad_status_text="VAD 未启用",
        )
