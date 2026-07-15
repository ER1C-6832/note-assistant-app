"""Pure Assistant Runtime reducer for Gate 2.1 and future runtime gates."""

from __future__ import annotations

from dataclasses import replace

from .effects import (
    AssistantEffect,
    CancelRuntimeEffects,
    CloseTransport,
    EnsureIdentity,
    OpenTransport,
    ResetIdentity,
    RunActivation,
    SendText,
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
    AudioCaptureStarted,
    AudioCaptureStopped,
    AudioCountersUpdated,
    AudioFailureSimulationRequested,
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
    StreamingSessionStarted,
    StreamingSessionStopped,
    StreamingTurnChanged,
    SystemAudioInterrupted,
    SystemAudioRecovered,
    TextSubmitted,
    TextTurnCompleted,
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
)
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
    VoiceActivityState,
)
from .transitions import Transition


class ConversationStateMachine:
    """Reduce one event into one immutable state replacement plus effects."""

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
            return self._assistant_text(current, event)
        if isinstance(event, TtsStateReceived):
            return self._tts_state(current, event)
        if isinstance(event, TextTurnCompleted):
            return self._text_turn_completed(current, event)
        if isinstance(event, ProtocolMessageObserved):
            return self._protocol_observed(current, event)
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
            return self._not_ready(current, event, AssistantCapability.AUTOMATIC_RECOVERY)
        if isinstance(
            event,
            (AudioCaptureStarted, AudioCaptureStopped, AudioCountersUpdated),
        ):
            return self._not_ready(current, event, AssistantCapability.PUSH_TO_TALK)
        if isinstance(
            event,
            (PlaybackStarted, PlaybackEnded, PlaybackCountersUpdated),
        ):
            return self._not_ready(current, event, AssistantCapability.TTS_PLAYBACK)
        if isinstance(event, VoiceActivityChanged):
            return self._not_ready(current, event, AssistantCapability.VAD)
        if isinstance(
            event,
            (StreamingSessionStarted, StreamingTurnChanged, StreamingSessionStopped),
        ):
            return self._not_ready(current, event, AssistantCapability.STREAMING_CONVERSATION)
        if isinstance(event, BargeInTriggered):
            return self._not_ready(current, event, AssistantCapability.BARGE_IN)
        if isinstance(event, MicrophoneLeaseChanged):
            return self._not_ready(current, event, AssistantCapability.MICROPHONE_OWNERSHIP)
        if isinstance(event, (McpRequestReceived, McpRequestCompleted)):
            return self._not_ready(current, event, AssistantCapability.MCP_PROTOCOL)
        if isinstance(event, (WakeWordDetected, KwsStateChanged)):
            return self._not_ready(current, event, AssistantCapability.KWS)
        if isinstance(event, RuntimeOverloaded):
            return self._error(
                current,
                event,
                code="runtime_overloaded",
                message=event.message,
                category=AssistantErrorCategory.RUNTIME,
                recoverable=True,
            )
        if isinstance(event, VoiceInteractionModeRequested):
            return self._not_ready(current, event, AssistantCapability.STREAMING_CONVERSATION)
        if isinstance(event, StreamingBargeInRequested):
            return self._not_ready(current, event, AssistantCapability.BARGE_IN)
        if isinstance(event, (PushToTalkStartRequested, PushToTalkStopRequested)):
            return self._not_ready(current, event, AssistantCapability.PUSH_TO_TALK)
        if isinstance(
            event,
            (StreamingConversationStartRequested, StreamingConversationStopRequested),
        ):
            return self._not_ready(current, event, AssistantCapability.STREAMING_CONVERSATION)
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
                code="assistant_disabled",
                message="助手未启用，不能连接",
                category=AssistantErrorCategory.VALIDATION,
                recoverable=True,
            )
        if current.connection.status is AssistantConnectionStatus.CONNECTED:
            return self._transition(replace(current, status_text="助手已经连接", error=None), event)
        if current.connection.status is AssistantConnectionStatus.CONNECTING:
            return self._transition(replace(current, status_text="助手正在连接"), event)

        generation = current.connection.connection_generation + 1
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
        return self._transition(
            state,
            event,
            (OpenTransport(generation=generation, runtime_mode=current.runtime_mode),),
        )

    def _reconnect(self, current: AssistantState, event: ReconnectRequested) -> Transition:
        if not current.enabled:
            return self._error(
                current,
                event,
                code="assistant_disabled",
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
                reconnect_attempt=current.recovery.reconnect_attempt + 1,
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
                recovery=replace(current.recovery, manual_disconnect_requested=True),
                status_text="助手连接已关闭",
                error=None,
            )
            return self._transition(state, event)

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
                next_reconnect_at_ns=None,
                manual_disconnect_requested=True,
                last_reconnect_decision="manual_disconnect",
            ),
            status_text="正在断开助手连接",
            error=None,
        )
        effects = (
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
                code="empty_text",
                message="文本不能为空",
                category=AssistantErrorCategory.VALIDATION,
                recoverable=True,
                preserve_phase=True,
            )
        if not current.is_connected:
            return self._error(
                current,
                event,
                code="assistant_not_connected",
                message="助手未连接，不能发送文本",
                category=AssistantErrorCategory.TRANSPORT,
                recoverable=True,
            )
        if current.conversation.active_text_turn_token is not None:
            return self._error(
                current,
                event,
                code="text_turn_in_progress",
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
            status_text=(
                "Scripted Fake Runtime 已连接"
                if current.runtime_mode is AssistantRuntimeMode.FAKE
                else "真实 WebSocket hello/session 已验证"
            ),
            error=None,
        )
        return self._transition(state, event)

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

        connection = replace(
            current.connection,
            status=AssistantConnectionStatus.DISCONNECTED,
            session_id=None,
            close_code=event.code,
            close_reason=event.reason,
        )
        expected = (
            event.expected
            or event.code == 1000
            or current.recovery.manual_disconnect_requested
            or not current.enabled
        )
        if expected:
            state = replace(
                current,
                phase=(AssistantPhase.IDLE if current.enabled else AssistantPhase.DISABLED),
                connection=connection,
                audio=self._idle_audio(current.audio),
                conversation=self._idle_conversation(current.conversation),
                recovery=replace(
                    current.recovery,
                    last_reconnect_decision="expected_close_no_reconnect",
                    next_reconnect_at_ns=None,
                ),
                status_text=f"助手连接已关闭：{event.reason}",
                error=None,
            )
            return self._transition(state, event)

        disconnected = replace(current, connection=connection)
        return self._error(
            disconnected,
            event,
            code="transport_closed_abnormally",
            message=f"助手连接异常关闭：{event.reason}",
            category=AssistantErrorCategory.TRANSPORT,
            recoverable=True,
            details=f"close_code={event.code}",
        )

    def _transport_failed(self, current: AssistantState, event: TransportFailed) -> Transition:
        if self._is_stale_connection_event(current, event.generation):
            return Transition.unchanged(current)
        disconnected = replace(
            current,
            connection=replace(
                current.connection,
                status=AssistantConnectionStatus.DISCONNECTED,
                session_id=None,
                connection_generation=event.generation + 1,
                close_reason=event.message,
            ),
            conversation=self._idle_conversation(current.conversation),
        )
        return self._error(
            disconnected,
            event,
            code="transport_failure",
            message=event.message,
            category=AssistantErrorCategory.TRANSPORT,
            recoverable=True,
            effects=(
                CancelRuntimeEffects(reason="transport_failure"),
                CloseTransport(generation=event.generation, reason="transport_failure"),
            ),
        )

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
        effects: list[AssistantEffect] = [CancelRuntimeEffects(reason="identity_reset")]
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
            code="effect_execution_failed",
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
            push_to_talk_stop_latency_ms=None,
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
            assistant_reply_buffer="",
            streaming_state=StreamingConversationState.INACTIVE,
            streaming_session_active=False,
            streaming_generation=(conversation.streaming_generation + int(invalidate_streaming)),
            streaming_session_id=None,
            streaming_turn_index=0,
            barge_in_monitor_active=False,
            vad_state=VoiceActivityState.DISABLED,
            vad_status_text="VAD 未启用",
        )
