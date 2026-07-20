from __future__ import annotations

from dataclasses import replace

from app.assistant.effects import StartStreamingConversation
from app.assistant.playback.models import PlaybackSummary
from app.assistant.playback.runtime_effects import AbortPlaybackTurn
from app.assistant.playback.runtime_events import (
    AcousticBargeInConfirmed,
    ActualPlaybackEnded,
)
from app.assistant.playback.two_turn_state_machine import TwoTurnConversationStateMachine
from app.assistant.state import (
    AssistantAudioStatus,
    AssistantConnectionStatus,
    AssistantEntrySource,
    AssistantPhase,
    AssistantState,
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
            session_id="connection-session",
            connection_generation=3,
        ),
        audio=replace(
            disabled.audio,
            status=AssistantAudioStatus.PLAYING,
            capture_generation=4,
            playback_generation=7,
            microphone_owner=MicrophoneOwner.NONE,
            decoded_frames=960,
            played_frames=480,
            last_audio_summary="playback_active stream=7 packets=3",
        ),
        conversation=replace(
            disabled.conversation,
            preferred_voice_mode=VoiceInteractionMode.STREAMING_CONVERSATION,
            active_entry_source=AssistantEntrySource.STREAMING_BUTTON,
            voice_turn_counter=11,
            active_voice_turn_token=None,
            last_completed_voice_turn_token=11,
            streaming_session_active=True,
            streaming_generation=2,
            streaming_session_id="streaming-session",
            streaming_turn_index=1,
            active_streaming_turn_token=None,
            last_completed_streaming_turn_token=11,
            streaming_state=StreamingConversationState.SPEAKING,
            streaming_barge_in_enabled=True,
        ),
    )
    state.validate()
    return state


def _confirmed() -> AcousticBargeInConfirmed:
    return AcousticBargeInConfirmed(
        at_ns=100,
        connection_generation=3,
        streaming_generation=2,
        playback_generation=7,
        monitor_generation=9,
        next_capture_generation=5,
    )


def test_confirmed_barge_in_cancels_old_turn_and_allocates_exactly_one_next_turn() -> None:
    reducer = TwoTurnConversationStateMachine()
    transition = reducer.reduce(_playing_state(), _confirmed())

    assert transition.state.phase is AssistantPhase.CONNECTED
    assert transition.state.audio.status is AssistantAudioStatus.IDLE
    assert transition.state.audio.capture_generation == 5
    assert transition.state.audio.microphone_owner is MicrophoneOwner.ASSISTANT_CAPTURE
    assert transition.state.conversation.barge_in_trigger_count == 1
    assert transition.state.conversation.streaming_turn_index == 2
    assert transition.state.conversation.active_streaming_turn_token == 12
    assert [type(effect) for effect in transition.effects] == [
        AbortPlaybackTurn,
        StartStreamingConversation,
    ]
    abort, start = transition.effects
    assert abort.turn_token == 11
    assert abort.playback_generation == 7
    assert start.turn_token == 12
    assert start.capture_generation == 5

    duplicate = reducer.reduce(transition.state, _confirmed())
    assert duplicate.state == transition.state
    assert duplicate.effects == ()


def test_cancelled_playback_cannot_reopen_microphone_via_late_natural_end() -> None:
    reducer = TwoTurnConversationStateMachine()
    interrupted = reducer.reduce(_playing_state(), _confirmed()).state
    summary = PlaybackSummary(
        connection_generation=3,
        stream_sequence=7,
        playback_generation=7,
        turn_token=11,
        streaming_generation=2,
        reason="tts_stop",
        natural_end=True,
        encoded_packets_received=3,
        encoded_bytes_received=192,
        decoded_chunks=3,
        decoded_sample_frames=960,
        played_sample_frames=960,
        encoded_overflow_count=0,
        pcm_overflow_count=0,
        pcm_underflow_count=0,
        buffer_peak_bytes=3840,
        output_device_public_name="Speakers",
    )
    late = reducer.reduce(
        interrupted,
        ActualPlaybackEnded(at_ns=101, summary=summary),
    )
    assert late.state == interrupted
    assert late.effects == ()


def test_stale_generation_and_disabled_preference_are_rejected() -> None:
    reducer = TwoTurnConversationStateMachine()
    state = _playing_state()
    stale = replace(_confirmed(), playback_generation=6)
    assert reducer.reduce(state, stale).effects == ()

    disabled = replace(
        state,
        conversation=replace(state.conversation, streaming_barge_in_enabled=False),
    )
    assert reducer.reduce(disabled, _confirmed()).effects == ()
