from __future__ import annotations

from dataclasses import replace

import pytest

from app.assistant.effects import StartStreamingConversation
from app.assistant.playback.models import PlaybackSummary
from app.assistant.playback.runtime_events import (
    ActualPlaybackEnded,
    RuntimePlaybackCancelled,
    RuntimePlaybackFailed,
)
from app.assistant.playback.two_turn_state_machine import (
    TwoTurnConversationStateMachine,
)
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
            last_completed_voice_turn_token=1,
            streaming_session_active=True,
            streaming_generation=1,
            streaming_session_id="streaming-session",
            streaming_turn_index=1,
            last_completed_streaming_turn_token=1,
            streaming_state=StreamingConversationState.SPEAKING,
        ),
    )
    state.validate()
    return state


def _summary(
    *,
    connection_generation: int = 1,
    playback_generation: int = 1,
    turn_token: int = 1,
    streaming_generation: int | None = 1,
    natural_end: bool = True,
    played_sample_frames: int = 2_880,
) -> PlaybackSummary:
    return PlaybackSummary(
        connection_generation=connection_generation,
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
        played_sample_frames=played_sample_frames,
        encoded_overflow_count=0,
        pcm_overflow_count=0,
        pcm_underflow_count=0,
        buffer_peak_bytes=11_520,
        output_device_public_name="Speakers",
    )


def _next_count(transition) -> int:
    return sum(isinstance(effect, StartStreamingConversation) for effect in transition.effects)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda state: replace(
            state,
            conversation=replace(
                state.conversation,
                streaming_state=StreamingConversationState.STOPPING,
            ),
        ),
        lambda state: replace(
            state,
            conversation=replace(
                state.conversation,
                preferred_voice_mode=VoiceInteractionMode.HOLD_TO_TALK,
            ),
        ),
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
    ],
)
def test_precedence_matrix_suppresses_late_physical_end(mutator) -> None:
    reducer = TwoTurnConversationStateMachine()
    current = mutator(_playing_state())

    transition = reducer.reduce(
        current,
        ActualPlaybackEnded(at_ns=100, summary=_summary()),
    )

    assert _next_count(transition) == 0


@pytest.mark.parametrize(
    "summary",
    [
        _summary(connection_generation=2),
        _summary(playback_generation=2),
        _summary(turn_token=2),
        _summary(streaming_generation=2),
        _summary(natural_end=False),
        _summary(played_sample_frames=0),
    ],
)
def test_invalid_or_stale_end_never_allocates_capture(summary) -> None:
    reducer = TwoTurnConversationStateMachine()
    transition = reducer.reduce(
        _playing_state(),
        ActualPlaybackEnded(at_ns=110, summary=summary),
    )
    assert _next_count(transition) == 0


def test_cancel_and_failure_terminal_paths_never_auto_next() -> None:
    reducer = TwoTurnConversationStateMachine()
    state = _playing_state()

    cancelled = reducer.reduce(
        state,
        RuntimePlaybackCancelled(
            at_ns=120,
            connection_generation=1,
            stream_sequence=1,
            playback_generation=1,
            turn_token=1,
            reason="user_stop",
        ),
    )
    late_after_cancel = reducer.reduce(
        cancelled.state,
        ActualPlaybackEnded(at_ns=121, summary=_summary()),
    )
    assert _next_count(late_after_cancel) == 0

    failed = reducer.reduce(
        state,
        RuntimePlaybackFailed(
            at_ns=122,
            connection_generation=1,
            stream_sequence=1,
            playback_generation=1,
            turn_token=1,
            code="output_device_failed",
            message="device failed",
        ),
    )
    late_after_failure = reducer.reduce(
        failed.state,
        ActualPlaybackEnded(at_ns=123, summary=_summary()),
    )
    assert _next_count(late_after_failure) == 0


def test_only_current_natural_physical_end_allocates_exactly_once() -> None:
    reducer = TwoTurnConversationStateMachine()
    first = reducer.reduce(
        _playing_state(),
        ActualPlaybackEnded(at_ns=130, summary=_summary()),
    )
    duplicate = reducer.reduce(
        first.state,
        ActualPlaybackEnded(at_ns=131, summary=_summary()),
    )

    assert _next_count(first) == 1
    assert _next_count(duplicate) == 0
    assert first.state.audio.capture_generation == 2
    assert first.state.conversation.streaming_turn_index == 2
    assert first.state.conversation.active_streaming_turn_token == 2
