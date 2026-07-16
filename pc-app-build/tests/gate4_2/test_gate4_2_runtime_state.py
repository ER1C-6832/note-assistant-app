from __future__ import annotations

from dataclasses import replace

from app.assistant.effects import StartStreamingConversation
from app.assistant.events import TtsStateReceived
from app.assistant.playback.models import PlaybackSummary
from app.assistant.playback.runtime_effects import StartActualPlayback
from app.assistant.playback.runtime_events import (
    ActualPlaybackEnded,
    ActualPlaybackStarted,
    PlaybackProgressUpdated,
    TtsPlaybackInputEnded,
    TtsPlaybackStreamStarted,
)
from app.assistant.playback.runtime_state_machine import (
    PlaybackConversationStateMachine,
)
from app.assistant.protocol import DownlinkAudioFormat
from app.assistant.state import (
    AssistantAudioStatus,
    AssistantConnectionStatus,
    AssistantEntrySource,
    AssistantPhase,
    AssistantState,
    StreamingConversationState,
)


def _streaming_thinking_state() -> AssistantState:
    disabled = AssistantState.disabled(now_ns=0)
    state = replace(
        disabled,
        enabled=True,
        phase=AssistantPhase.THINKING,
        connection=replace(
            disabled.connection,
            status=AssistantConnectionStatus.CONNECTED,
            session_id="session-1",
            connection_generation=1,
        ),
        audio=replace(disabled.audio, capture_generation=1),
        conversation=replace(
            disabled.conversation,
            active_entry_source=AssistantEntrySource.STREAMING_BUTTON,
            voice_turn_counter=1,
            active_voice_turn_token=1,
            streaming_session_active=True,
            streaming_generation=1,
            streaming_session_id="local-session",
            streaming_turn_index=1,
            active_streaming_turn_token=1,
            streaming_state=StreamingConversationState.THINKING,
        ),
        status_text="等待回复",
    )
    state.validate()
    return state


def test_terminal_json_does_not_end_playback_and_actual_drain_does_not_auto_next() -> None:
    reducer = PlaybackConversationStateMachine()
    current = _streaming_thinking_state()
    wire = DownlinkAudioFormat("opus", 24_000, 1, 20.0)

    started_stream = reducer.reduce(
        current,
        TtsPlaybackStreamStarted(
            at_ns=10,
            connection_generation=1,
            stream_sequence=1,
            playback_generation=1,
            turn_token=1,
            wire_format=wire,
        ),
    )
    assert started_stream.state.phase is AssistantPhase.THINKING
    assert started_stream.state.audio.status is AssistantAudioStatus.IDLE
    assert sum(isinstance(effect, StartActualPlayback) for effect in started_stream.effects) == 1

    terminal_json = reducer.reduce(
        started_stream.state,
        TtsStateReceived(
            at_ns=11,
            generation=1,
            state="stop",
            turn_token=1,
            session_id="session-1",
        ),
    )
    assert terminal_json.state.phase is AssistantPhase.THINKING
    assert terminal_json.state.conversation.streaming_state is StreamingConversationState.THINKING

    playing = reducer.reduce(
        terminal_json.state,
        ActualPlaybackStarted(
            at_ns=12,
            connection_generation=1,
            stream_sequence=1,
            playback_generation=1,
            turn_token=1,
            output_device_public_name="Speakers",
        ),
    )
    assert playing.state.phase is AssistantPhase.SPEAKING
    assert playing.state.audio.status is AssistantAudioStatus.PLAYING

    input_ended = reducer.reduce(
        playing.state,
        TtsPlaybackInputEnded(
            at_ns=13,
            connection_generation=1,
            stream_sequence=1,
            playback_generation=1,
            turn_token=1,
            reason="tts_stop",
        ),
    )
    assert input_ended.state.phase is AssistantPhase.SPEAKING

    progress = reducer.reduce(
        input_ended.state,
        PlaybackProgressUpdated(
            at_ns=14,
            connection_generation=1,
            stream_sequence=1,
            playback_generation=1,
            turn_token=1,
            decoded_sample_frames=960,
            played_sample_frames=960,
            encoded_packets_received=1,
            pcm_underflow_count=0,
            encoded_overflow_count=0,
            pcm_overflow_count=0,
        ),
    )
    summary = PlaybackSummary(
        connection_generation=1,
        stream_sequence=1,
        playback_generation=1,
        turn_token=1,
        streaming_generation=1,
        reason="tts_stop",
        natural_end=True,
        encoded_packets_received=1,
        encoded_bytes_received=64,
        decoded_chunks=1,
        decoded_sample_frames=960,
        played_sample_frames=960,
        encoded_overflow_count=0,
        pcm_overflow_count=0,
        pcm_underflow_count=0,
        buffer_peak_bytes=3_840,
        output_device_public_name="Speakers",
    )
    ended = reducer.reduce(
        progress.state,
        ActualPlaybackEnded(at_ns=15, summary=summary),
    )
    assert ended.state.phase is AssistantPhase.CONNECTED
    assert ended.state.audio.status is AssistantAudioStatus.IDLE
    assert (
        ended.state.conversation.streaming_state is StreamingConversationState.WAITING_FOR_NEXT_TURN
    )
    assert not any(isinstance(effect, StartStreamingConversation) for effect in ended.effects)

    duplicate = reducer.reduce(
        ended.state,
        ActualPlaybackEnded(at_ns=16, summary=summary),
    )
    assert duplicate.state == ended.state
    assert duplicate.effects == ()


def test_late_tts_state_cannot_clear_playback_failure() -> None:
    from app.assistant.playback.runtime_events import RuntimePlaybackFailed

    reducer = PlaybackConversationStateMachine()
    current = _streaming_thinking_state()
    failed = reducer.reduce(
        current,
        RuntimePlaybackFailed(
            at_ns=20,
            connection_generation=1,
            stream_sequence=1,
            playback_generation=1,
            turn_token=1,
            code="output_device_unavailable",
            message="default output device unavailable",
        ),
    )
    assert failed.state.phase is AssistantPhase.ERROR
    assert failed.state.error is not None

    late_terminal = reducer.reduce(
        failed.state,
        TtsStateReceived(
            at_ns=21,
            generation=1,
            state="stop",
            turn_token=1,
            session_id="session-1",
        ),
    )
    assert late_terminal.state.phase is AssistantPhase.ERROR
    assert late_terminal.state.audio.status is AssistantAudioStatus.ERROR
    assert late_terminal.state.error == failed.state.error
    assert late_terminal.state.conversation.streaming_state is StreamingConversationState.ERROR
