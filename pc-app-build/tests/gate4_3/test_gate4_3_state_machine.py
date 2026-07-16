from __future__ import annotations

from dataclasses import replace

import pytest

from app.assistant.effects import StartStreamingConversation
from app.assistant.events import AudioCaptureFailed
from app.assistant.playback.models import PlaybackSummary
from app.assistant.playback.runtime_events import (
    ActualPlaybackEnded,
    RuntimePlaybackFailed,
)
from app.assistant.playback.two_turn_state_machine import (
    TwoTurnConversationStateMachine,
)
from app.assistant.state import (
    AssistantAudioStatus,
    AssistantCapability,
    AssistantConnectionStatus,
    AssistantEntrySource,
    AssistantPhase,
    AssistantState,
    CapabilityStatus,
    MicrophoneOwner,
    StreamingConversationState,
    VoiceInteractionMode,
)


def _playing_state() -> AssistantState:
    disabled = AssistantState.disabled(now_ns=0)
    state = replace(
        disabled,
        enabled=True,
        phase=AssistantPhase.SPEAKING,
        connection=replace(
            disabled.connection,
            status=AssistantConnectionStatus.CONNECTED,
            session_id="session-1",
            connection_generation=1,
        ),
        audio=replace(
            disabled.audio,
            status=AssistantAudioStatus.PLAYING,
            capture_generation=1,
            playback_generation=1,
            microphone_owner=MicrophoneOwner.NONE,
            decoded_frames=960,
            played_frames=960,
            last_audio_summary="playback_active stream=1 packets=1",
        ),
        conversation=replace(
            disabled.conversation,
            preferred_voice_mode=VoiceInteractionMode.STREAMING_CONVERSATION,
            active_entry_source=AssistantEntrySource.STREAMING_BUTTON,
            voice_turn_counter=1,
            active_voice_turn_token=None,
            last_completed_voice_turn_token=1,
            streaming_session_active=True,
            streaming_generation=1,
            streaming_session_id="streaming-session",
            streaming_turn_index=1,
            active_streaming_turn_token=None,
            last_completed_streaming_turn_token=1,
            streaming_state=StreamingConversationState.SPEAKING,
        ),
        status_text="正在播放",
    )
    state.validate()
    return state


def _summary(
    *,
    playback_generation: int = 1,
    turn_token: int = 1,
    streaming_generation: int | None = 1,
    natural_end: bool = True,
) -> PlaybackSummary:
    return PlaybackSummary(
        connection_generation=1,
        stream_sequence=playback_generation,
        playback_generation=playback_generation,
        turn_token=turn_token,
        streaming_generation=streaming_generation,
        reason="tts_stop",
        natural_end=natural_end,
        encoded_packets_received=3,
        encoded_bytes_received=192,
        decoded_chunks=3,
        decoded_sample_frames=2_880,
        played_sample_frames=2_880,
        encoded_overflow_count=0,
        pcm_overflow_count=0,
        pcm_underflow_count=0,
        buffer_peak_bytes=11_520,
        output_device_public_name="Speakers",
    )


def _next_effect(transition):
    return [
        effect for effect in transition.effects if isinstance(effect, StartStreamingConversation)
    ]


def test_actual_playback_ended_allocates_one_next_turn() -> None:
    reducer = TwoTurnConversationStateMachine()
    transition = reducer.reduce(
        _playing_state(),
        ActualPlaybackEnded(at_ns=100, summary=_summary()),
    )

    assert transition.state.phase is AssistantPhase.CONNECTED
    assert transition.state.audio.status is AssistantAudioStatus.IDLE
    assert transition.state.audio.capture_generation == 2
    assert transition.state.audio.microphone_owner is MicrophoneOwner.NONE
    assert transition.state.conversation.streaming_state is StreamingConversationState.STARTING
    assert transition.state.conversation.streaming_turn_index == 2
    assert transition.state.conversation.voice_turn_counter == 2
    assert transition.state.conversation.active_voice_turn_token == 2
    assert transition.state.conversation.active_streaming_turn_token == 2
    assert transition.state.conversation.last_completed_streaming_turn_token == 1

    effects = _next_effect(transition)
    assert len(effects) == 1
    effect = effects[0]
    assert effect.connection_generation == 1
    assert effect.streaming_generation == 1
    assert effect.capture_generation == 2
    assert effect.turn_token == 2
    assert effect.turn_index == 2
    assert effect.session_id == "streaming-session"

    streaming = next(
        item
        for item in transition.state.capabilities
        if item.name is AssistantCapability.STREAMING_CONVERSATION
    )
    assert streaming.status is CapabilityStatus.ACTIVE
    assert streaming.target_gate == "4.3"

    duplicate = reducer.reduce(
        transition.state,
        ActualPlaybackEnded(at_ns=101, summary=_summary()),
    )
    assert duplicate.state == transition.state
    assert _next_effect(duplicate) == []


@pytest.mark.parametrize(
    ("mutator", "expected"),
    [
        (
            lambda state: replace(
                state,
                conversation=replace(
                    state.conversation,
                    streaming_state=StreamingConversationState.STOPPING,
                ),
            ),
            0,
        ),
        (
            lambda state: replace(
                state,
                enabled=False,
                phase=AssistantPhase.DISABLED,
                connection=replace(
                    state.connection,
                    status=AssistantConnectionStatus.DISCONNECTED,
                    session_id=None,
                ),
                audio=replace(state.audio, status=AssistantAudioStatus.IDLE),
            ),
            0,
        ),
        (
            lambda state: replace(
                state,
                conversation=replace(
                    state.conversation,
                    preferred_voice_mode=VoiceInteractionMode.HOLD_TO_TALK,
                ),
            ),
            0,
        ),
    ],
)
def test_stop_disable_and_mode_switch_precede_late_playback_end(mutator, expected) -> None:
    reducer = TwoTurnConversationStateMachine()
    current = mutator(_playing_state())
    transition = reducer.reduce(
        current,
        ActualPlaybackEnded(at_ns=110, summary=_summary()),
    )
    assert len(_next_effect(transition)) == expected


def test_stale_or_uncorrelated_playback_end_is_noop() -> None:
    reducer = TwoTurnConversationStateMachine()
    state = _playing_state()

    stale_generation = reducer.reduce(
        state,
        ActualPlaybackEnded(
            at_ns=120,
            summary=_summary(playback_generation=2),
        ),
    )
    assert stale_generation.state == state
    assert _next_effect(stale_generation) == []

    wrong_turn = reducer.reduce(
        state,
        ActualPlaybackEnded(
            at_ns=121,
            summary=_summary(turn_token=9),
        ),
    )
    assert _next_effect(wrong_turn) == []

    wrong_session = reducer.reduce(
        state,
        ActualPlaybackEnded(
            at_ns=122,
            summary=_summary(streaming_generation=2),
        ),
    )
    assert _next_effect(wrong_session) == []


def test_playback_failure_never_allocates_next_turn() -> None:
    reducer = TwoTurnConversationStateMachine()
    state = _playing_state()
    failed = reducer.reduce(
        state,
        RuntimePlaybackFailed(
            at_ns=130,
            connection_generation=1,
            stream_sequence=1,
            playback_generation=1,
            turn_token=1,
            code="output_device_failed",
            message="device failed",
        ),
    )
    assert failed.state.phase is AssistantPhase.ERROR

    late_end = reducer.reduce(
        failed.state,
        ActualPlaybackEnded(at_ns=131, summary=_summary()),
    )
    assert _next_effect(late_end) == []
    assert late_end.state.error == failed.state.error


def test_non_natural_end_never_allocates_next_turn() -> None:
    reducer = TwoTurnConversationStateMachine()
    transition = reducer.reduce(
        _playing_state(),
        ActualPlaybackEnded(
            at_ns=140,
            summary=_summary(natural_end=False),
        ),
    )
    assert transition.state.phase is AssistantPhase.ERROR
    assert _next_effect(transition) == []


def test_next_capture_start_failure_closes_session_and_never_reallocates() -> None:
    reducer = TwoTurnConversationStateMachine()
    allocated = reducer.reduce(
        _playing_state(),
        ActualPlaybackEnded(at_ns=150, summary=_summary()),
    )
    failed = reducer.reduce(
        allocated.state,
        AudioCaptureFailed(
            at_ns=151,
            generation=2,
            connection_generation=1,
            turn_token=2,
            code="microphone_busy",
            message="next capture failed",
        ),
    )
    assert failed.state.error is not None
    assert not failed.state.conversation.streaming_session_active
    assert _next_effect(failed) == []

    late_duplicate = reducer.reduce(
        failed.state,
        ActualPlaybackEnded(at_ns=152, summary=_summary()),
    )
    assert _next_effect(late_duplicate) == []
