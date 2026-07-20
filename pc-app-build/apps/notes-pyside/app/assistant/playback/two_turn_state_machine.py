"""Gate 4.3 actual-PlaybackEnded auto-next-turn reducer extension."""

from __future__ import annotations

from dataclasses import replace

from ..effects import AssistantEffect, StartStreamingConversation
from ..state import (
    AssistantAudioStatus,
    AssistantCapability,
    AssistantEntrySource,
    AssistantPhase,
    AssistantState,
    CapabilityState,
    CapabilityStatus,
    MicrophoneOwner,
    StreamingConversationState,
    VoiceActivityState,
    VoiceInteractionMode,
)
from ..transitions import Transition
from .models import PlaybackSummary
from .runtime_effects import AbortPlaybackTurn
from .runtime_events import AcousticBargeInConfirmed, ActualPlaybackEnded
from .runtime_state_machine import PlaybackConversationStateMachine


class TwoTurnConversationStateMachine(PlaybackConversationStateMachine):
    """Allocate one next streaming capture only from actual physical PlaybackEnded."""

    def reduce(self, current: AssistantState, event) -> Transition:
        if isinstance(event, AcousticBargeInConfirmed):
            return self._acoustic_barge_in_confirmed(current, event)
        return super().reduce(current, event)

    def _acoustic_barge_in_confirmed(
        self,
        current: AssistantState,
        event: AcousticBargeInConfirmed,
    ) -> Transition:
        conversation = current.conversation
        if (
            not current.enabled
            or not current.is_connected
            or not conversation.streaming_barge_in_enabled
            or not conversation.streaming_session_active
            or conversation.preferred_voice_mode is not VoiceInteractionMode.STREAMING_CONVERSATION
            or current.phase not in {AssistantPhase.THINKING, AssistantPhase.SPEAKING}
            or not self._playback_active(current)
            or event.connection_generation != current.connection.connection_generation
            or event.streaming_generation != conversation.streaming_generation
            or event.playback_generation != current.audio.playback_generation
            or event.next_capture_generation != current.audio.capture_generation + 1
            or conversation.active_text_turn_token is not None
        ):
            return Transition.unchanged(current)

        old_turn_token = (
            conversation.active_streaming_turn_token
            or conversation.active_voice_turn_token
            or conversation.last_completed_streaming_turn_token
            or conversation.last_completed_voice_turn_token
        )
        if old_turn_token is None or old_turn_token <= 0:
            return Transition.unchanged(current)
        next_turn_token = max(conversation.voice_turn_counter, old_turn_token) + 1
        next_turn_index = max(1, conversation.streaming_turn_index) + 1
        source = conversation.active_entry_source or AssistantEntrySource.STREAMING_BUTTON
        next_conversation = replace(
            conversation,
            active_entry_source=source,
            last_user_text=None,
            last_stt_text=None,
            last_assistant_text=None,
            last_assistant_source_type=None,
            assistant_reply_buffer="",
            voice_turn_counter=next_turn_token,
            active_voice_turn_token=next_turn_token,
            active_voice_turn_started_at_ns=event.at_ns,
            pending_voice_turn_completion_token=None,
            last_completed_voice_turn_token=max(
                conversation.last_completed_voice_turn_token,
                old_turn_token,
            ),
            last_voice_turn_completed_at_ns=event.at_ns,
            streaming_turn_index=next_turn_index,
            active_streaming_turn_token=next_turn_token,
            last_completed_streaming_turn_token=max(
                conversation.last_completed_streaming_turn_token,
                old_turn_token,
            ),
            streaming_state=StreamingConversationState.STARTING,
            streaming_response_deadline_ns=None,
            barge_in_monitor_active=False,
            barge_in_trigger_count=conversation.barge_in_trigger_count + 1,
            vad_state=VoiceActivityState.WARMUP,
            vad_status_text="VAD 准备中",
        )
        next_state = replace(
            current,
            phase=AssistantPhase.CONNECTED,
            audio=replace(
                current.audio,
                status=AssistantAudioStatus.IDLE,
                capture_generation=event.next_capture_generation,
                microphone_owner=MicrophoneOwner.ASSISTANT_CAPTURE,
                active_capture_mode=None,
                captured_frames=0,
                encoded_frames=0,
                uploaded_frames=0,
                dropped_pcm_frames=0,
                uplink_overflow_count=0,
                decoded_frames=0,
                played_frames=0,
                last_audio_summary=(
                    f"acoustic_barge_in playback={event.playback_generation} "
                    f"monitor={event.monitor_generation}"
                ),
            ),
            conversation=next_conversation,
            capabilities=self._activate_barge_in_capability(current.capabilities),
            status_text=f"已打断回复，正在聆听第 {next_turn_index} 轮",
            error=None,
        )
        effects: tuple[AssistantEffect, ...] = (
            AbortPlaybackTurn(
                connection_generation=event.connection_generation,
                playback_generation=event.playback_generation,
                turn_token=old_turn_token,
                capture_generation=current.audio.capture_generation,
                reason="acoustic_barge_in",
            ),
            StartStreamingConversation(
                connection_generation=event.connection_generation,
                streaming_generation=conversation.streaming_generation,
                capture_generation=event.next_capture_generation,
                turn_token=next_turn_token,
                turn_index=next_turn_index,
                requested_at_ns=event.at_ns,
                idle_timeout_ms=conversation.streaming_idle_timeout_ms,
                source=source,
                session_id=conversation.streaming_session_id,
            ),
        )
        return self._finish(next_state, event, effects)

    def _playback_ended(
        self,
        current: AssistantState,
        event: ActualPlaybackEnded,
    ) -> Transition:
        # Disable/disconnect/cancel already owns terminal cleanup. A physical-drain
        # callback that arrives afterwards is stale and must not re-enter either the
        # Gate 4.2 cleanup path or the Gate 4.3 auto-next allocation path.
        if (
            not current.enabled
            or not current.is_connected
            or current.phase is AssistantPhase.DISABLED
            or not self._playback_active(current)
        ):
            return Transition.unchanged(current)

        completed = super()._playback_ended(current, event)
        summary = event.summary
        if not self._auto_next_allowed(current, completed.state, summary):
            return completed

        state = completed.state
        conversation = state.conversation
        next_turn_token = max(conversation.voice_turn_counter, summary.turn_token) + 1
        next_capture_generation = state.audio.capture_generation + 1
        next_turn_index = max(1, conversation.streaming_turn_index) + 1
        source = conversation.active_entry_source or AssistantEntrySource.STREAMING_BUTTON

        audio = replace(
            state.audio,
            status=AssistantAudioStatus.IDLE,
            capture_generation=next_capture_generation,
            microphone_owner=MicrophoneOwner.NONE,
            active_capture_mode=None,
            captured_frames=0,
            encoded_frames=0,
            uploaded_frames=0,
            dropped_pcm_frames=0,
            uplink_overflow_count=0,
            first_pcm_latency_ms=None,
            first_opus_latency_ms=None,
            first_opus_upload_latency_ms=None,
            stop_listen_latency_ms=None,
            input_device_public_name=None,
        )
        conversation = replace(
            conversation,
            active_entry_source=source,
            last_user_text=None,
            last_stt_text=None,
            last_assistant_text=None,
            last_assistant_source_type=None,
            assistant_reply_buffer="",
            voice_turn_counter=next_turn_token,
            active_voice_turn_token=next_turn_token,
            active_voice_turn_started_at_ns=event.at_ns,
            pending_voice_turn_completion_token=None,
            last_completed_voice_turn_token=max(
                conversation.last_completed_voice_turn_token,
                summary.turn_token,
            ),
            last_voice_turn_completed_at_ns=event.at_ns,
            streaming_turn_index=next_turn_index,
            active_streaming_turn_token=next_turn_token,
            last_completed_streaming_turn_token=max(
                conversation.last_completed_streaming_turn_token,
                summary.turn_token,
            ),
            streaming_state=StreamingConversationState.STARTING,
            streaming_response_deadline_ns=None,
            vad_state=VoiceActivityState.WARMUP,
            vad_status_text="VAD 准备中",
        )
        next_state = replace(
            state,
            phase=AssistantPhase.CONNECTED,
            audio=audio,
            conversation=conversation,
            capabilities=self._activate_two_turn_capability(state.capabilities),
            status_text=f"语音回复播放完成，正在自动开启第 {next_turn_index} 轮",
            error=None,
        )
        effect = StartStreamingConversation(
            connection_generation=state.connection.connection_generation,
            streaming_generation=conversation.streaming_generation,
            capture_generation=next_capture_generation,
            turn_token=next_turn_token,
            turn_index=next_turn_index,
            requested_at_ns=event.at_ns,
            idle_timeout_ms=conversation.streaming_idle_timeout_ms,
            source=source,
            session_id=conversation.streaming_session_id,
        )
        effects: tuple[AssistantEffect, ...] = (*completed.effects, effect)
        return self._finish(next_state, event, effects)

    @staticmethod
    def _auto_next_allowed(
        before: AssistantState,
        after: AssistantState,
        summary: PlaybackSummary,
    ) -> bool:
        conversation = before.conversation
        if (
            not summary.natural_end
            or summary.played_sample_frames <= 0
            or summary.connection_generation != before.connection.connection_generation
            or summary.playback_generation != before.audio.playback_generation
            or summary.streaming_generation != conversation.streaming_generation
            or not before.enabled
            or not before.is_connected
            or before.error is not None
            or not conversation.streaming_session_active
            or conversation.preferred_voice_mode is not VoiceInteractionMode.STREAMING_CONVERSATION
            or conversation.streaming_state
            in {
                StreamingConversationState.STOPPING,
                StreamingConversationState.ERROR,
                StreamingConversationState.RECOVERING,
            }
            or before.audio.status is AssistantAudioStatus.RECORDING
            or before.audio.microphone_owner is not MicrophoneOwner.NONE
            or conversation.active_text_turn_token is not None
            or after.error is not None
            or after.audio.status is not AssistantAudioStatus.IDLE
            or after.conversation.streaming_state
            is not StreamingConversationState.WAITING_FOR_NEXT_TURN
        ):
            return False

        correlated_tokens = {
            token
            for token in (
                conversation.active_voice_turn_token,
                conversation.active_streaming_turn_token,
                conversation.last_completed_voice_turn_token,
                conversation.last_completed_streaming_turn_token,
            )
            if token is not None and token > 0
        }
        if summary.turn_token not in correlated_tokens:
            return False
        if any(token > summary.turn_token for token in correlated_tokens):
            return False
        return True

    @staticmethod
    def _activate_two_turn_capability(
        capabilities: tuple[CapabilityState, ...],
    ) -> tuple[CapabilityState, ...]:
        return tuple(
            (
                CapabilityState(
                    name=item.name,
                    status=CapabilityStatus.ACTIVE,
                    target_gate="4.3",
                    detail=(
                        "actual PlaybackEnded 唯一触发自动续轮；"
                        "真实两轮连续对话与 generation 防重复"
                    ),
                )
                if item.name is AssistantCapability.STREAMING_CONVERSATION
                else item
            )
            for item in capabilities
        )

    @staticmethod
    def _activate_barge_in_capability(
        capabilities: tuple[CapabilityState, ...],
    ) -> tuple[CapabilityState, ...]:
        return tuple(
            (
                CapabilityState(
                    name=item.name,
                    status=CapabilityStatus.ACTIVE,
                    target_gate="6.3+6.4",
                    detail="本地 AEC 处理监听、声学插话和原子麦克风交接",
                )
                if item.name is AssistantCapability.STREAMING_CONVERSATION
                else item
            )
            for item in capabilities
        )


ConversationStateMachine = TwoTurnConversationStateMachine
