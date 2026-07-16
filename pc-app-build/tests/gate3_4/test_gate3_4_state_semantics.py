from __future__ import annotations

from dataclasses import replace

import pytest

from app.assistant.effects import (
    CancelRuntimeEffects,
    CancelStreamingResponseTimeout,
    ScheduleReconnect,
    StartStreamingConversation,
    StopStreamingConversation,
)
from app.assistant.events import (
    AssistantTextReceived,
    AudioCaptureStarted,
    ConnectRequested,
    EnableRequested,
    PlaybackEnded,
    ServerHelloReceived,
    StreamingConversationStartRequested,
    StreamingConversationStopRequested,
    StreamingResponseTimeout,
    StreamingSessionStarted,
    StreamingSessionStopped,
    StreamingTurnSubmitted,
    TransportClosed,
    TtsStateReceived,
    UseFakeRuntimeRequested,
    VoiceInteractionModeRequested,
    VoiceTurnCompleted,
)
from app.assistant.state import (
    AssistantAudioStatus,
    AssistantPhase,
    AssistantState,
    MicrophoneOwner,
    StreamingConversationState,
    VoiceActivityState,
    VoiceInteractionMode,
)
from app.assistant.state_machine import ConversationStateMachine


def _started_streaming_state() -> (
    tuple[ConversationStateMachine, AssistantState, StartStreamingConversation]
):
    machine = ConversationStateMachine()
    state = AssistantState.disabled(now_ns=1)
    state = machine.reduce(state, EnableRequested(at_ns=2)).state
    state = machine.reduce(state, UseFakeRuntimeRequested(at_ns=3)).state
    opening = machine.reduce(state, ConnectRequested(at_ns=4))
    state = machine.reduce(
        opening.state,
        ServerHelloReceived(at_ns=5, generation=2, session_id="gate3-4-session"),
    ).state
    state = machine.reduce(
        state,
        VoiceInteractionModeRequested(
            at_ns=6,
            mode=VoiceInteractionMode.STREAMING_CONVERSATION,
        ),
    ).state
    started = machine.reduce(
        state,
        StreamingConversationStartRequested(at_ns=7, permission_granted=True),
    )
    assert len(started.effects) == 1
    effect = started.effects[0]
    assert isinstance(effect, StartStreamingConversation)
    state = machine.reduce(
        started.state,
        StreamingSessionStarted(
            at_ns=8,
            generation=effect.streaming_generation,
            connection_generation=effect.connection_generation,
            capture_generation=effect.capture_generation,
            turn_token=effect.turn_token,
            turn_index=effect.turn_index,
            session_id="local-streaming-session",
        ),
    ).state
    state = machine.reduce(
        state,
        AudioCaptureStarted(
            at_ns=9,
            generation=effect.capture_generation,
            connection_generation=effect.connection_generation,
            turn_token=effect.turn_token,
            input_device_public_name="Fake microphone",
        ),
    ).state
    return machine, state, effect


def _thinking_state() -> (
    tuple[ConversationStateMachine, AssistantState, StartStreamingConversation]
):
    machine, state, effect = _started_streaming_state()
    state = replace(
        state,
        phase=AssistantPhase.UPLOADING_AUDIO,
        audio=replace(
            state.audio,
            status=AssistantAudioStatus.IDLE,
            microphone_owner=MicrophoneOwner.NONE,
            active_capture_mode=None,
        ),
        conversation=replace(
            state.conversation,
            streaming_state=StreamingConversationState.SUBMITTING_TURN,
            vad_state=VoiceActivityState.END_OF_SPEECH,
        ),
    )
    state = machine.reduce(
        state,
        StreamingTurnSubmitted(
            at_ns=10,
            generation=effect.streaming_generation,
            connection_generation=effect.connection_generation,
            capture_generation=effect.capture_generation,
            turn_token=effect.turn_token,
            turn_index=effect.turn_index,
            captured_frames=25,
            encoded_frames=25,
            uploaded_frames=25,
            speech_seen=True,
            stop_listen_latency_ms=40,
        ),
    ).state
    return machine, state, effect


@pytest.mark.parametrize(
    ("event_factory", "source_type"),
    (
        (
            lambda effect: AssistantTextReceived(
                at_ns=11,
                generation=effect.connection_generation,
                turn_token=effect.turn_token,
                session_id="gate3-4-session",
                source_type="text",
                text="好的",
            ),
            "text",
        ),
        (
            lambda effect: TtsStateReceived(
                at_ns=11,
                generation=effect.connection_generation,
                turn_token=effect.turn_token,
                session_id="gate3-4-session",
                state="sentence_end",
                text="好的",
            ),
            "tts",
        ),
    ),
)
def test_valid_assistant_transcript_parks_session_without_auto_next_turn(
    event_factory,
    source_type: str,
) -> None:
    machine, thinking, effect = _thinking_state()

    replied = machine.reduce(thinking, event_factory(effect))

    assert (
        replied.state.conversation.streaming_state
        is StreamingConversationState.WAITING_FOR_NEXT_TURN
    )
    assert replied.state.conversation.streaming_session_active is True
    assert replied.state.conversation.last_assistant_text == "好的"
    assert replied.state.conversation.last_assistant_source_type == source_type
    assert replied.state.audio.status is AssistantAudioStatus.IDLE
    assert replied.state.audio.microphone_owner is MicrophoneOwner.NONE
    assert replied.state.conversation.streaming_response_deadline_ns is None
    assert replied.effects == (CancelStreamingResponseTimeout(),)
    assert not any(isinstance(item, StartStreamingConversation) for item in replied.effects)


def test_playback_ended_is_not_activated_before_gate4() -> None:
    machine, waiting, effect = _thinking_state()
    waiting = machine.reduce(
        waiting,
        AssistantTextReceived(
            at_ns=11,
            generation=effect.connection_generation,
            turn_token=effect.turn_token,
            session_id="gate3-4-session",
            source_type="text",
            text="好的",
        ),
    ).state

    playback = machine.reduce(
        waiting,
        PlaybackEnded(at_ns=12, generation=effect.streaming_generation),
    )

    assert (
        playback.state.conversation.streaming_state
        is StreamingConversationState.WAITING_FOR_NEXT_TURN
    )
    assert playback.state.conversation.streaming_session_active is True
    assert not any(isinstance(item, StartStreamingConversation) for item in playback.effects)


def test_voice_turn_completes_once_and_late_reply_is_a_noop_for_current_turn() -> None:
    machine, thinking, effect = _thinking_state()
    replied = machine.reduce(
        thinking,
        AssistantTextReceived(
            at_ns=11,
            generation=effect.connection_generation,
            turn_token=effect.turn_token,
            session_id="gate3-4-session",
            source_type="text",
            text="好的",
        ),
    ).state
    completed = machine.reduce(
        replied,
        VoiceTurnCompleted(
            at_ns=12,
            generation=effect.connection_generation,
            capture_generation=effect.capture_generation,
            turn_token=effect.turn_token,
            reason="reply_complete",
            had_stt_text=True,
            had_assistant_text=True,
        ),
    )
    assert completed.state.conversation.active_voice_turn_token is None
    assert completed.state.conversation.active_streaming_turn_token is None
    assert completed.state.conversation.last_completed_streaming_turn_token == effect.turn_token

    late = machine.reduce(
        completed.state,
        AssistantTextReceived(
            at_ns=13,
            generation=effect.connection_generation,
            turn_token=effect.turn_token,
            session_id="gate3-4-session",
            source_type="text",
            text="迟到重复回复",
        ),
    )
    assert late.effects == ()
    assert late.state.conversation.last_completed_streaming_turn_token == effect.turn_token
    assert late.state.conversation.last_assistant_text == "好的"


def test_stale_connection_session_and_turn_tokens_are_harmless() -> None:
    machine, thinking, effect = _thinking_state()
    stale_events = (
        AssistantTextReceived(
            at_ns=11,
            generation=effect.connection_generation - 1,
            turn_token=effect.turn_token,
            session_id="gate3-4-session",
            text="旧 generation",
        ),
        AssistantTextReceived(
            at_ns=12,
            generation=effect.connection_generation,
            turn_token=effect.turn_token + 1,
            session_id="gate3-4-session",
            text="旧 turn",
        ),
        AssistantTextReceived(
            at_ns=13,
            generation=effect.connection_generation,
            turn_token=effect.turn_token,
            session_id="different-session",
            text="旧 session",
        ),
        StreamingResponseTimeout(
            at_ns=14,
            generation=effect.streaming_generation + 1,
            turn_token=effect.turn_token,
        ),
    )

    state = thinking
    for event in stale_events:
        transition = machine.reduce(state, event)
        assert transition.effects == ()
        state = transition.state

    assert state.conversation.streaming_state is StreamingConversationState.THINKING
    assert state.conversation.last_assistant_text is None


def test_timeout_then_session_stop_then_repeated_user_stop_finalizes_once() -> None:
    machine, thinking, effect = _thinking_state()
    timed_out = machine.reduce(
        thinking,
        StreamingResponseTimeout(
            at_ns=11,
            generation=effect.streaming_generation,
            turn_token=effect.turn_token,
        ),
    )
    stop_effects = [
        item for item in timed_out.effects if isinstance(item, StopStreamingConversation)
    ]
    assert len(stop_effects) == 1

    stopped = machine.reduce(
        timed_out.state,
        StreamingSessionStopped(
            at_ns=12,
            generation=effect.streaming_generation,
            turn_token=effect.turn_token,
            reason="streaming_response_timeout",
        ),
    )
    repeated = machine.reduce(
        stopped.state,
        StreamingConversationStopRequested(at_ns=13, reason="late_user_stop"),
    )

    assert stopped.state.conversation.streaming_session_active is False
    assert stopped.state.conversation.streaming_state is StreamingConversationState.INACTIVE
    assert repeated.effects == ()
    assert repeated.state.conversation.streaming_session_active is False


def test_stop_then_late_end_of_speech_does_not_finalize_again() -> None:
    from app.assistant.events import VoiceActivityChanged

    machine, listening, effect = _started_streaming_state()
    stopping = machine.reduce(
        listening,
        StreamingConversationStopRequested(at_ns=20, reason="user_stop"),
    )
    assert sum(isinstance(item, StopStreamingConversation) for item in stopping.effects) == 1

    late_vad = machine.reduce(
        stopping.state,
        VoiceActivityChanged(
            at_ns=21,
            generation=effect.capture_generation,
            connection_generation=effect.connection_generation,
            streaming_generation=effect.streaming_generation,
            turn_token=effect.turn_token,
            frame_sequence=99,
            state=VoiceActivityState.END_OF_SPEECH,
            status_text="late end of speech",
        ),
    )
    assert late_vad.effects == ()
    assert late_vad.state.conversation.streaming_state is StreamingConversationState.STOPPING


def test_waiting_manual_stop_and_late_repeated_stop_complete_session_once() -> None:
    machine, thinking, effect = _thinking_state()
    waiting = machine.reduce(
        thinking,
        AssistantTextReceived(
            at_ns=20,
            generation=effect.connection_generation,
            turn_token=effect.turn_token,
            session_id="gate3-4-session",
            source_type="text",
            text="完成",
        ),
    ).state
    stopping = machine.reduce(
        waiting,
        StreamingConversationStopRequested(at_ns=21, reason="manual_stop"),
    )
    assert sum(isinstance(item, StopStreamingConversation) for item in stopping.effects) == 1

    stopped = machine.reduce(
        stopping.state,
        StreamingSessionStopped(
            at_ns=22,
            generation=effect.streaming_generation,
            turn_token=effect.turn_token,
            reason="manual_stop",
        ),
    ).state
    repeated = machine.reduce(
        stopped,
        StreamingConversationStopRequested(at_ns=23, reason="duplicate_stop"),
    )
    assert repeated.effects == ()
    assert repeated.state.conversation.streaming_session_active is False
    assert repeated.state.conversation.streaming_state is StreamingConversationState.INACTIVE


def test_uplink_overflow_ends_streaming_capture_without_leaking_logical_lease() -> None:
    from app.assistant.effects import CancelRuntimeEffects
    from app.assistant.events import AudioUplinkOverflow

    machine, listening, effect = _started_streaming_state()
    failed = machine.reduce(
        listening,
        AudioUplinkOverflow(
            at_ns=30,
            generation=effect.capture_generation,
            connection_generation=effect.connection_generation,
            turn_token=effect.turn_token,
            message="bounded packet queue overflow",
        ),
    )

    assert failed.state.conversation.streaming_session_active is False
    assert failed.state.audio.status is AssistantAudioStatus.IDLE
    assert failed.state.audio.microphone_owner is MicrophoneOwner.NONE
    assert failed.effects == (CancelRuntimeEffects(reason="audio_capture_failed"),)


def test_disable_invalidates_late_streaming_reply_and_timeout() -> None:
    from app.assistant.events import DisableRequested

    machine, thinking, effect = _thinking_state()
    disabled = machine.reduce(thinking, DisableRequested(at_ns=40))
    assert disabled.state.enabled is False
    assert disabled.state.phase is AssistantPhase.DISABLED
    assert disabled.state.connection.connection_generation > effect.connection_generation

    late_reply = machine.reduce(
        disabled.state,
        AssistantTextReceived(
            at_ns=41,
            generation=effect.connection_generation,
            turn_token=effect.turn_token,
            session_id="gate3-4-session",
            text="late reply",
        ),
    )
    late_timeout = machine.reduce(
        late_reply.state,
        StreamingResponseTimeout(
            at_ns=42,
            generation=effect.streaming_generation,
            turn_token=effect.turn_token,
        ),
    )
    assert late_reply.effects == ()
    assert late_timeout.effects == ()
    assert late_timeout.state.phase is AssistantPhase.DISABLED


def test_disconnect_during_thinking_enters_recovery_without_auto_capture() -> None:
    machine, thinking, effect = _thinking_state()

    closed = machine.reduce(
        thinking,
        TransportClosed(
            at_ns=50,
            generation=effect.connection_generation,
            code=1006,
            reason="gate3_4_thinking_disconnect",
            expected=False,
        ),
    )

    assert closed.state.conversation.streaming_state is StreamingConversationState.RECOVERING
    assert closed.state.conversation.streaming_session_active is True
    assert any(isinstance(item, CancelRuntimeEffects) for item in closed.effects)
    assert any(isinstance(item, ScheduleReconnect) for item in closed.effects)
    assert not any(isinstance(item, StartStreamingConversation) for item in closed.effects)


@pytest.mark.parametrize(
    "order",
    (
        ("timeout", "stop", "disconnect"),
        ("stop", "disconnect", "timeout"),
        ("disconnect", "timeout", "stop"),
    ),
)
def test_timeout_stop_disconnect_orders_emit_at_most_one_turn_stop(order) -> None:
    machine, state, effect = _thinking_state()
    stop_effect_count = 0

    for index, name in enumerate(order, start=1):
        if name == "timeout":
            event = StreamingResponseTimeout(
                at_ns=60 + index,
                generation=effect.streaming_generation,
                turn_token=effect.turn_token,
            )
        elif name == "stop":
            event = StreamingConversationStopRequested(
                at_ns=60 + index,
                reason="gate3_4_ordered_stop",
            )
        else:
            event = TransportClosed(
                at_ns=60 + index,
                generation=effect.connection_generation,
                code=1006,
                reason="gate3_4_ordered_disconnect",
                expected=False,
            )
        transition = machine.reduce(state, event)
        stop_effect_count += sum(
            isinstance(item, StopStreamingConversation) for item in transition.effects
        )
        assert not any(isinstance(item, StartStreamingConversation) for item in transition.effects)
        state = transition.state

    assert stop_effect_count <= 1
    assert state.audio.status is AssistantAudioStatus.IDLE
    assert state.audio.microphone_owner is MicrophoneOwner.NONE
