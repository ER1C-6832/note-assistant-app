from __future__ import annotations

import struct

import pytest

from app.assistant import (
    AssistantAudioStatus,
    AssistantController,
    AssistantPhase,
    ConversationStateMachine,
    StreamingConversationState,
    VoiceActivityState,
    VoiceInteractionMode,
)
from app.assistant.audio import (
    AssistantAudioEngine,
    FakeCaptureScript,
    FakeOpusEncoder,
    MicrophoneLeaseCoordinator,
    ScriptedFakeAudioCapture,
    ScriptedVoiceActivityDetector,
)
from app.assistant.network import ReconnectPolicy
from app.assistant.testing import FakeClock, OpenSucceeded, ScriptedFakeTransport, VoiceReply


def _frames(count: int, sample: int = 1400) -> tuple[bytes, ...]:
    payload = struct.pack("<320h", *([sample] * 320))
    return tuple(payload for _ in range(count))


def _controller(*, states, frames, replies=(), opens=None):
    clock = FakeClock()
    capture = ScriptedFakeAudioCapture(FakeCaptureScript.from_frames(frames))
    engine = AssistantAudioEngine(
        capture=capture,
        encoder_factory=FakeOpusEncoder,
        vad_factory=lambda _timeout: ScriptedVoiceActivityDetector(states),
    )
    transport = ScriptedFakeTransport(
        clock=clock,
        open_steps=opens or (OpenSucceeded(session_id="gate3-3-session"),),
        voice_steps=replies,
    )
    controller = AssistantController(
        transport=transport,
        state_machine=ConversationStateMachine(
            ReconnectPolicy(jitter_fraction=0.0, backoff_seconds=(0.01, 0.02, 0.03))
        ),
        clock=clock,
        audio_engine=engine,
        microphone_coordinator=MicrophoneLeaseCoordinator(),
    )
    return controller, capture, transport


async def _connect_streaming(controller: AssistantController) -> None:
    await controller.enable_assistant()
    await controller.use_fake_runtime()
    await controller.connect()
    await controller.wait_for_state(lambda state: state.is_connected)
    await controller.set_voice_interaction_mode(VoiceInteractionMode.STREAMING_CONVERSATION)


@pytest.mark.asyncio
async def test_vad_auto_submits_one_streaming_turn_and_keeps_session_until_manual_stop() -> None:
    states = (
        VoiceActivityState.WARMUP,
        VoiceActivityState.WAITING_FOR_SPEECH,
        VoiceActivityState.SPEECH_DETECTED,
        VoiceActivityState.SPEECH_ACTIVE,
        VoiceActivityState.END_OF_SPEECH,
    )
    controller, capture, transport = _controller(
        states=states,
        frames=_frames(len(states)),
        replies=(VoiceReply(stt_text="记录客户报价", assistant_text="好的"),),
    )
    try:
        await _connect_streaming(controller)
        await controller.start_streaming_conversation(permission_granted=True)
        started = await controller.wait_for_state(
            lambda state: state.conversation.streaming_session_active
            and state.audio.status is AssistantAudioStatus.RECORDING
        )
        assert started.conversation.streaming_session_id
        assert started.conversation.streaming_turn_index == 1
        assert capture.emit_all() == len(states)

        replied = await controller.wait_for_state(
            lambda state: state.conversation.streaming_state
            is StreamingConversationState.WAITING_FOR_NEXT_TURN
            and state.conversation.last_assistant_text == "好的",
            timeout_seconds=3.0,
        )
        assert replied.conversation.streaming_session_active is True
        assert replied.conversation.last_user_text == "记录客户报价"
        assert replied.audio.uploaded_frames == len(states)
        assert replied.diagnostics.vad_speech_started_count == 1
        assert replied.diagnostics.vad_speech_ended_count == 1
        assert len(transport.listen_start_calls) == 1
        assert len(transport.listen_stop_calls) == 1
        assert controller.streaming_vad_running is False
        assert controller.audio_capture_active is False

        await controller.stop_streaming_conversation("test_manual_stop")
        stopped = await controller.wait_for_state(
            lambda state: not state.conversation.streaming_session_active
        )
        assert stopped.phase is AssistantPhase.CONNECTED
        assert controller.streaming_response_timer_running is False
        assert controller.microphone_lease_generation is None
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_no_speech_timeout_aborts_and_ends_streaming_session() -> None:
    states = (
        VoiceActivityState.WARMUP,
        VoiceActivityState.WAITING_FOR_SPEECH,
        VoiceActivityState.NO_SPEECH_TIMEOUT,
    )
    controller, capture, transport = _controller(
        states=states,
        frames=_frames(len(states), sample=0),
    )
    try:
        await _connect_streaming(controller)
        await controller.start_streaming_conversation(True)
        await controller.wait_for_state(
            lambda state: state.audio.status is AssistantAudioStatus.RECORDING
        )
        capture.emit_all()
        stopped = await controller.wait_for_state(
            lambda state: not state.conversation.streaming_session_active,
            timeout_seconds=3.0,
        )
        assert stopped.phase is AssistantPhase.CONNECTED
        assert transport.listen_stop_calls == []
        assert transport.abort_calls
        assert controller.audio_worker_alive is False
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_mode_switch_stops_active_streaming_before_persisting_new_mode() -> None:
    states = (VoiceActivityState.WARMUP, VoiceActivityState.WAITING_FOR_SPEECH)
    controller, _, transport = _controller(states=states, frames=_frames(len(states), 0))
    try:
        await _connect_streaming(controller)
        await controller.start_streaming_conversation(True)
        await controller.wait_for_state(
            lambda state: state.conversation.streaming_session_active
            and state.audio.status is AssistantAudioStatus.RECORDING
        )
        await controller.set_voice_interaction_mode(VoiceInteractionMode.HOLD_TO_TALK)
        stopped = await controller.wait_for_state(
            lambda state: not state.conversation.streaming_session_active
        )
        assert stopped.conversation.preferred_voice_mode is VoiceInteractionMode.HOLD_TO_TALK
        assert transport.abort_calls
        assert controller.microphone_lease_generation is None
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_abnormal_close_moves_streaming_session_to_recovering_and_resumes_once() -> None:
    states = (VoiceActivityState.WARMUP, VoiceActivityState.WAITING_FOR_SPEECH)
    controller, _, transport = _controller(
        states=states,
        frames=_frames(len(states), 0),
        opens=(
            OpenSucceeded(session_id="gate3-3-session-1"),
            OpenSucceeded(session_id="gate3-3-session-2"),
        ),
    )
    try:
        await _connect_streaming(controller)
        await controller.start_streaming_conversation(True)
        first = await controller.wait_for_state(
            lambda state: state.conversation.streaming_session_active
            and state.audio.status is AssistantAudioStatus.RECORDING
        )
        local_session_id = first.conversation.streaming_session_id
        first_generation = first.connection.connection_generation
        await transport.emit_server_close(code=1006, reason="gate3_3_streaming_close")
        recovering = await controller.wait_for_state(
            lambda state: state.conversation.streaming_state
            is StreamingConversationState.RECOVERING
        )
        assert recovering.conversation.streaming_session_id == local_session_id
        resumed = await controller.wait_for_state(
            lambda state: state.is_connected
            and state.connection.connection_generation > first_generation
            and state.audio.status is AssistantAudioStatus.RECORDING,
            timeout_seconds=3.0,
        )
        assert resumed.conversation.streaming_session_id == local_session_id
        assert len(transport.listen_start_calls) == 2
    finally:
        await controller.shutdown()
