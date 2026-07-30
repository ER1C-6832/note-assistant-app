from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from app.assistant.effects import (
    CancelRuntimeEffects,
    ScheduleVoiceCompletionCleanupTimeout,
)
from app.assistant.playback.runtime_effects import StartActualPlayback
from app.assistant.events import (
    VoiceCompletionCleanupTimeout,
    VoiceTurnCompleted,
)
from app.assistant.playback.runtime_events import TtsPlaybackStreamStarted
from app.assistant.playback.runtime_state_machine import (
    PlaybackConversationStateMachine,
)
from app.assistant.protocol import DownlinkAudioFormat
from app.assistant.runtime_trace import RuntimeTrace
from app.assistant.state import (
    AssistantAudioStatus,
    AssistantConnectionStatus,
    AssistantEntrySource,
    AssistantPhase,
    AssistantState,
    MicrophoneOwner,
    StreamingConversationState,
)
from app.assistant.state_machine import ConversationStateMachine


def active_voice_state(
    *,
    audio_status=AssistantAudioStatus.RECORDING,
    streaming_state=StreamingConversationState.SUBMITTING_TURN,
) -> AssistantState:
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
        audio=replace(
            disabled.audio,
            status=audio_status,
            capture_generation=1,
            microphone_owner=(
                MicrophoneOwner.ASSISTANT_CAPTURE
                if audio_status is AssistantAudioStatus.RECORDING
                else MicrophoneOwner.NONE
            ),
            active_capture_mode=(
                "streaming"
                if audio_status is AssistantAudioStatus.RECORDING
                else None
            ),
        ),
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
            streaming_state=streaming_state,
        ),
    )
    state.validate()
    return state


def completed_event() -> VoiceTurnCompleted:
    return VoiceTurnCompleted(
        at_ns=10,
        generation=1,
        capture_generation=1,
        turn_token=1,
        reason="tts_stop",
        had_stt_text=True,
        had_assistant_text=True,
    )


def test_pending_capture_cleanup_has_bounded_recovery() -> None:
    reducer = ConversationStateMachine()
    pending = reducer.reduce(active_voice_state(), completed_event())
    assert pending.state.phase is AssistantPhase.THINKING
    assert pending.state.conversation.pending_voice_turn_completion_token == 1
    assert any(
        isinstance(effect, ScheduleVoiceCompletionCleanupTimeout)
        for effect in pending.effects
    )

    recovered = reducer.reduce(
        pending.state,
        VoiceCompletionCleanupTimeout(
            at_ns=20,
            connection_generation=1,
            capture_generation=1,
            turn_token=1,
        ),
    )
    assert recovered.state.phase is AssistantPhase.CONNECTED
    assert recovered.state.audio.status is AssistantAudioStatus.IDLE
    assert recovered.state.conversation.pending_voice_turn_completion_token is None
    assert recovered.state.conversation.streaming_session_active is False
    assert any(isinstance(effect, CancelRuntimeEffects) for effect in recovered.effects)


def test_tts_start_during_streaming_stop_race_is_not_cancelled() -> None:
    reducer = PlaybackConversationStateMachine()
    transition = reducer.reduce(
        active_voice_state(),
        TtsPlaybackStreamStarted(
            at_ns=11,
            connection_generation=1,
            stream_sequence=1,
            playback_generation=1,
            turn_token=1,
            wire_format=DownlinkAudioFormat("opus", 24_000, 1, 20.0),
        ),
    )
    assert transition.state.error is None
    assert any(isinstance(effect, StartActualPlayback) for effect in transition.effects)


def test_text_reply_without_playback_stream_is_explicit_and_terminal() -> None:
    reducer = PlaybackConversationStateMachine()
    transition = reducer.reduce(
        active_voice_state(
            audio_status=AssistantAudioStatus.IDLE,
            streaming_state=StreamingConversationState.THINKING,
        ),
        completed_event(),
    )
    assert transition.state.phase is AssistantPhase.CONNECTED
    assert transition.state.error is not None
    assert transition.state.error.code == "tts_audio_missing"
    assert "未收到可播放" in transition.state.status_text


def test_runtime_trace_never_records_conversation_text(tmp_path) -> None:
    path = tmp_path / "pc-runtime.log"
    trace = RuntimeTrace(path)
    state = active_voice_state(audio_status=AssistantAudioStatus.IDLE)
    event = SimpleNamespace(
        at_ns=12,
        text="公司机密便签正文",
        turn_token=1,
    )
    trace.event(event=event, before=state, after=state, effects=())
    trace.close()
    payload = path.read_text(encoding="utf-8")
    assert "公司机密便签正文" not in payload
    assert "SimpleNamespace" in payload
