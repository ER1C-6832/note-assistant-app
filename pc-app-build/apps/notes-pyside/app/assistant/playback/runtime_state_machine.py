"""Playback-aware reducer extension preserving the Gate 1-3 state machine."""

from __future__ import annotations

from dataclasses import replace

from ..effects import AssistantEffect, CancelStreamingResponseTimeout
from ..events import AssistantTextReceived, TtsStateReceived, VoiceTurnCompleted
from ..state import (
    AssistantAudioStatus,
    AssistantCapability,
    AssistantError,
    AssistantErrorCategory,
    AssistantPhase,
    AssistantRuntimeMode,
    AssistantState,
    CapabilityState,
    CapabilityStatus,
    StreamingConversationState,
)
from ..state_machine import ConversationStateMachine
from ..transitions import Transition
from .runtime_effects import CancelActualPlayback, StartActualPlayback
from .runtime_events import (
    ActualPlaybackEnded,
    ActualPlaybackStarted,
    PlaybackProgressUpdated,
    RuntimePlaybackCancelled,
    RuntimePlaybackFailed,
    TtsPlaybackInputEnded,
    TtsPlaybackStreamStarted,
)


class PlaybackConversationStateMachine(ConversationStateMachine):
    """Activate Gate 4.2 playback without changing Gate 4.3 auto-next semantics."""

    def reduce(self, current: AssistantState, event) -> Transition:
        if isinstance(event, TtsPlaybackStreamStarted):
            return self._playback_stream_started(current, event)
        if isinstance(event, TtsPlaybackInputEnded):
            return self._playback_input_ended(current, event)
        if isinstance(event, ActualPlaybackStarted):
            return self._playback_started(current, event)
        if isinstance(event, PlaybackProgressUpdated):
            return self._playback_progress(current, event)
        if isinstance(event, ActualPlaybackEnded):
            return self._playback_ended(current, event)
        if isinstance(event, RuntimePlaybackCancelled):
            return self._playback_cancelled(current, event)
        if isinstance(event, RuntimePlaybackFailed):
            return self._playback_failed(current, event)
        if (
            self._playback_active(current)
            or self._playback_failed_state(current)
            or current.conversation.streaming_state is StreamingConversationState.STOPPING
        ) and isinstance(event, (AssistantTextReceived, TtsStateReceived, VoiceTurnCompleted)):
            return self._preserve_playback_terminal_owner(current, event)
        return super().reduce(current, event)

    def _playback_stream_started(
        self, current: AssistantState, event: TtsPlaybackStreamStarted
    ) -> Transition:
        if (
            not current.enabled
            or not current.is_connected
            or event.connection_generation != current.connection.connection_generation
            or event.playback_generation <= 0
            or event.stream_sequence <= 0
            or event.turn_token <= 0
        ):
            return Transition.unchanged(current)
        active_turns = {
            token
            for token in (
                current.conversation.active_voice_turn_token,
                current.conversation.active_text_turn_token,
            )
            if token is not None
        }
        if active_turns and event.turn_token not in active_turns:
            return Transition.unchanged(current)
        if event.streaming_generation is not None and (
            not current.conversation.streaming_session_active
            or event.streaming_generation != current.conversation.streaming_generation
        ):
            return Transition.unchanged(current)
        if current.audio.status is AssistantAudioStatus.RECORDING:
            state = replace(
                current,
                phase=AssistantPhase.ERROR,
                audio=replace(current.audio, status=AssistantAudioStatus.ERROR),
                status_text="播放启动被拒绝：麦克风采集尚未完全关闭",
                error=AssistantError(
                    code="capture_playback_overlap",
                    message="capture must close before playback starts",
                    category=AssistantErrorCategory.AUDIO,
                    recoverable=True,
                    source_event=type(event).__name__,
                    occurred_at_ns=event.at_ns,
                ),
            )
            return self._finish(
                state,
                event,
                (
                    CancelActualPlayback(
                        playback_generation=event.playback_generation,
                        reason="capture_playback_overlap",
                    ),
                ),
            )
        conversation = current.conversation
        if conversation.streaming_session_active:
            conversation = replace(
                conversation,
                streaming_state=StreamingConversationState.THINKING,
                streaming_response_deadline_ns=None,
            )
        wire = event.wire_format
        state = replace(
            current,
            phase=AssistantPhase.THINKING,
            audio=replace(
                current.audio,
                status=AssistantAudioStatus.IDLE,
                playback_generation=event.playback_generation,
                decoded_frames=0,
                played_frames=0,
                last_audio_summary=(
                    "playback_active "
                    f"stream={event.stream_sequence} packets=0 "
                    f"wire={wire.codec}/{wire.sample_rate_hz}/{wire.channels}/"
                    f"{wire.frame_duration_ms:g}ms"
                ),
            ),
            conversation=conversation,
            protocol=replace(
                current.protocol,
                last_protocol_event=f"TtsPlaybackStreamStarted:{event.stream_sequence}",
                last_protocol_error=None,
            ),
            status_text="正在缓冲语音回复",
            error=None,
        )
        effects: tuple[AssistantEffect, ...] = (
            StartActualPlayback(
                connection_generation=event.connection_generation,
                stream_sequence=event.stream_sequence,
                playback_generation=event.playback_generation,
                turn_token=event.turn_token,
            ),
            CancelStreamingResponseTimeout(),
        )
        return self._finish(state, event, effects)

    def _playback_input_ended(
        self, current: AssistantState, event: TtsPlaybackInputEnded
    ) -> Transition:
        if not self._matches(
            current, event.connection_generation, event.playback_generation
        ) or not self._playback_active(current):
            return Transition.unchanged(current)
        return self._finish(
            replace(
                current,
                protocol=replace(
                    current.protocol,
                    last_protocol_event=f"TtsPlaybackInputEnded:{event.reason}",
                ),
                status_text=(
                    "TTS 输入已结束，正在播放剩余缓冲"
                    if current.audio.status is AssistantAudioStatus.PLAYING
                    else "TTS 输入已结束，等待扬声器开始播放"
                ),
            ),
            event,
        )

    def _playback_started(
        self, current: AssistantState, event: ActualPlaybackStarted
    ) -> Transition:
        if (
            not self._matches(current, event.connection_generation, event.playback_generation)
            or not self._playback_active(current)
            or current.audio.status is AssistantAudioStatus.PLAYING
        ):
            return Transition.unchanged(current)
        conversation = current.conversation
        if conversation.streaming_session_active:
            conversation = replace(
                conversation,
                streaming_state=StreamingConversationState.SPEAKING,
                streaming_response_deadline_ns=None,
            )
        state = replace(
            current,
            phase=AssistantPhase.SPEAKING,
            audio=replace(
                current.audio,
                status=AssistantAudioStatus.PLAYING,
                last_audio_summary=(
                    f"playback_active stream={event.stream_sequence} "
                    f"device={event.output_device_public_name or 'default'}"
                ),
            ),
            conversation=conversation,
            capabilities=self._activate_playback_capability(current.capabilities),
            status_text="正在播放助手语音回复",
            error=None,
        )
        return self._finish(state, event)

    def _playback_progress(
        self, current: AssistantState, event: PlaybackProgressUpdated
    ) -> Transition:
        if not self._matches(
            current, event.connection_generation, event.playback_generation
        ) or not self._playback_active(current):
            return Transition.unchanged(current)
        summary = (
            "playback_active "
            f"stream={event.stream_sequence} packets={event.encoded_packets_received} "
            f"decoded={event.decoded_sample_frames} played={event.played_sample_frames} "
            f"underflow={event.pcm_underflow_count} "
            f"overflow={event.encoded_overflow_count + event.pcm_overflow_count}"
        )
        state = replace(
            current,
            audio=replace(
                current.audio,
                decoded_frames=event.decoded_sample_frames,
                played_frames=event.played_sample_frames,
                last_audio_summary=summary,
            ),
            diagnostics=replace(
                current.diagnostics,
                metrics_sample_count=current.diagnostics.metrics_sample_count + 1,
            ),
        )
        return self._finish(state, event)

    def _playback_ended(self, current: AssistantState, event: ActualPlaybackEnded) -> Transition:
        summary = event.summary
        if not self._matches(
            current, summary.connection_generation, summary.playback_generation
        ) or not self._playback_active(current):
            return Transition.unchanged(current)
        if not summary.natural_end or summary.played_sample_frames <= 0:
            failed = RuntimePlaybackFailed(
                at_ns=event.at_ns,
                connection_generation=summary.connection_generation,
                stream_sequence=summary.stream_sequence,
                playback_generation=summary.playback_generation,
                turn_token=summary.turn_token,
                code="playback_end_not_physical",
                message="playback ended without a natural device drain",
            )
            return self._playback_failed(current, failed)
        conversation = current.conversation
        status_text = "语音回复播放完成"
        if conversation.streaming_session_active:
            conversation = replace(
                conversation,
                streaming_state=StreamingConversationState.WAITING_FOR_NEXT_TURN,
                streaming_response_deadline_ns=None,
            )
            status_text = "语音回复播放完成；Gate 4.2 等待用户手动结束会话"
        state = replace(
            current,
            phase=AssistantPhase.CONNECTED,
            audio=replace(
                current.audio,
                status=AssistantAudioStatus.IDLE,
                decoded_frames=summary.decoded_sample_frames,
                played_frames=summary.played_sample_frames,
                last_audio_summary=(
                    f"playback_ended stream={summary.stream_sequence} "
                    f"packets={summary.encoded_packets_received} "
                    f"decoded={summary.decoded_sample_frames} "
                    f"played={summary.played_sample_frames} "
                    f"underflow={summary.pcm_underflow_count}"
                ),
            ),
            conversation=conversation,
            diagnostics=replace(
                current.diagnostics,
                gate_real_audio_playback_verified=(
                    current.diagnostics.gate_real_audio_playback_verified
                    or current.runtime_mode is AssistantRuntimeMode.REAL
                ),
            ),
            capabilities=self._activate_playback_capability(current.capabilities),
            status_text=status_text,
            error=None,
        )
        return self._finish(state, event)

    def _playback_cancelled(
        self, current: AssistantState, event: RuntimePlaybackCancelled
    ) -> Transition:
        if not self._matches(
            current, event.connection_generation, event.playback_generation
        ) or not self._playback_active(current):
            return Transition.unchanged(current)
        phase = AssistantPhase.CONNECTED if current.is_connected else current.phase
        conversation = current.conversation
        if conversation.streaming_session_active and conversation.streaming_state not in {
            StreamingConversationState.STOPPING,
            StreamingConversationState.ERROR,
        }:
            conversation = replace(
                conversation,
                streaming_state=StreamingConversationState.WAITING_FOR_NEXT_TURN,
            )
        state = replace(
            current,
            phase=phase,
            audio=replace(
                current.audio,
                status=AssistantAudioStatus.IDLE,
                last_audio_summary=f"playback_cancelled reason={event.reason}",
            ),
            conversation=conversation,
            status_text="语音播放已取消",
        )
        return self._finish(state, event)

    def _playback_failed(self, current: AssistantState, event: RuntimePlaybackFailed) -> Transition:
        if (
            event.connection_generation != current.connection.connection_generation
            or event.playback_generation < current.audio.playback_generation
            or (
                event.playback_generation == current.audio.playback_generation
                and current.audio.playback_generation > 0
                and not self._playback_active(current)
            )
        ):
            return Transition.unchanged(current)
        conversation = current.conversation
        if conversation.streaming_session_active:
            conversation = replace(
                conversation,
                streaming_state=StreamingConversationState.ERROR,
                streaming_response_deadline_ns=None,
            )
        state = replace(
            current,
            phase=AssistantPhase.ERROR,
            audio=replace(
                current.audio,
                status=AssistantAudioStatus.ERROR,
                playback_generation=max(
                    current.audio.playback_generation, event.playback_generation
                ),
                last_audio_summary=f"playback_failed code={event.code}",
            ),
            conversation=conversation,
            status_text=f"语音播放失败：{event.code}",
            error=AssistantError(
                code=event.code,
                message=event.message,
                category=AssistantErrorCategory.AUDIO,
                recoverable=True,
                source_event=type(event).__name__,
                occurred_at_ns=event.at_ns,
            ),
        )
        return self._finish(state, event)

    def _preserve_playback_terminal_owner(self, current: AssistantState, event) -> Transition:
        delegated = super().reduce(current, event)
        conversation = delegated.state.conversation
        if current.conversation.streaming_session_active:
            conversation = replace(
                conversation,
                streaming_state=current.conversation.streaming_state,
                streaming_response_deadline_ns=None,
            )
        state = replace(
            delegated.state,
            phase=current.phase,
            audio=current.audio,
            conversation=conversation,
            status_text=current.status_text,
            error=current.error,
        )
        effects = tuple(
            effect
            for effect in delegated.effects
            if isinstance(effect, CancelStreamingResponseTimeout)
        )
        return Transition(state=state, effects=effects).validated()

    @staticmethod
    def _playback_failed_state(state: AssistantState) -> bool:
        return bool(
            state.audio.status is AssistantAudioStatus.ERROR
            and (state.audio.last_audio_summary or "").startswith("playback_failed")
        )

    @staticmethod
    def _playback_active(state: AssistantState) -> bool:
        return bool(
            state.audio.playback_generation > 0
            and (state.audio.last_audio_summary or "").startswith("playback_active")
        )

    @staticmethod
    def _matches(
        state: AssistantState, connection_generation: int, playback_generation: int
    ) -> bool:
        return bool(
            connection_generation == state.connection.connection_generation
            and playback_generation == state.audio.playback_generation
            and playback_generation > 0
        )

    @staticmethod
    def _activate_playback_capability(
        capabilities: tuple[CapabilityState, ...],
    ) -> tuple[CapabilityState, ...]:
        return tuple(
            (
                CapabilityState(
                    name=item.name,
                    status=CapabilityStatus.ACTIVE,
                    target_gate="4.2",
                    detail="真实 Opus 下行、PyAV decode/resample、PyAudio physical drain",
                )
                if item.name is AssistantCapability.TTS_PLAYBACK
                else item
            )
            for item in capabilities
        )

    @staticmethod
    def _finish(
        state: AssistantState,
        event,
        effects: tuple[AssistantEffect, ...] = (),
    ) -> Transition:
        diagnostics = replace(
            state.diagnostics,
            last_event_name=type(event).__name__,
            last_event_at_ns=event.at_ns,
        )
        updated = replace(
            state,
            diagnostics=diagnostics,
            last_event_at_ns=event.at_ns,
        )
        return Transition(state=updated, effects=effects).validated()
