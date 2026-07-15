from __future__ import annotations

import asyncio
import struct

import pytest

from app.assistant import (
    AssistantAudioStatus,
    AssistantController,
    AssistantPhase,
    ConversationStateMachine,
)
from app.assistant.audio import (
    AssistantAudioEngine,
    FakeCaptureScript,
    FakeOpusEncoder,
    MicrophoneLeaseCoordinator,
    ScriptedFakeAudioCapture,
)
from app.assistant.network import ReconnectPolicy
from app.assistant.testing import FakeClock, OpenSucceeded, ScriptedFakeTransport, VoiceReply


def _speech_frames(count: int = 4) -> tuple[bytes, ...]:
    payload = struct.pack("<320h", *([1400] * 320))
    return tuple(payload for _ in range(count))


def _silence_frames(count: int = 3) -> tuple[bytes, ...]:
    payload = struct.pack("<320h", *([0] * 320))
    return tuple(payload for _ in range(count))


def _controller(frames: tuple[bytes, ...], *, replies=()):
    clock = FakeClock()
    capture = ScriptedFakeAudioCapture(FakeCaptureScript.from_frames(frames))
    engine = AssistantAudioEngine(capture=capture, encoder_factory=FakeOpusEncoder)
    transport = ScriptedFakeTransport(
        clock=clock,
        open_steps=(OpenSucceeded(session_id="gate3-2-session"),),
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


async def _connect(controller: AssistantController) -> None:
    await controller.enable_assistant()
    await controller.use_fake_runtime()
    await controller.connect()
    await controller.wait_for_state(lambda state: state.is_connected)


@pytest.mark.asyncio
async def test_fake_ptt_happy_path_uses_one_audio_pipeline() -> None:
    controller, capture, transport = _controller(
        _speech_frames(),
        replies=(VoiceReply(stt_text="记录报价", assistant_text="好的"),),
    )
    try:
        await _connect(controller)
        await controller.start_push_to_talk(permission_granted=True)
        recording = await controller.wait_for_state(
            lambda state: state.audio.status is AssistantAudioStatus.RECORDING
        )
        assert recording.phase is AssistantPhase.LISTENING
        assert capture.emit_all() == 4
        await asyncio.sleep(0.1)
        await controller.stop_push_to_talk()
        completed = await controller.wait_for_state(
            lambda state: state.conversation.last_completed_voice_turn_token == 1,
            timeout_seconds=2.0,
        )

        assert completed.phase is AssistantPhase.CONNECTED
        assert completed.conversation.last_user_text == "记录报价"
        assert completed.conversation.last_assistant_text == "好的"
        assert completed.audio.uploaded_frames == 4
        assert len(transport.listen_start_calls) == 1
        assert len(transport.listen_stop_calls) == 1
        assert len(transport.sent_audio_packets) == 4
        assert controller.audio_uplink_running is False
        assert controller.audio_worker_alive is False
        assert controller.microphone_lease_generation is None
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_no_speech_aborts_without_waiting_for_reply() -> None:
    controller, capture, transport = _controller(_silence_frames())
    try:
        await _connect(controller)
        await controller.start_push_to_talk(True)
        await controller.wait_for_state(
            lambda state: state.audio.status is AssistantAudioStatus.RECORDING
        )
        capture.emit_all()
        await asyncio.sleep(0.05)
        await controller.stop_push_to_talk()
        completed = await controller.wait_for_state(
            lambda state: state.conversation.last_completed_voice_turn_token == 1,
            timeout_seconds=2.0,
        )
        assert completed.phase is AssistantPhase.CONNECTED
        assert transport.listen_stop_calls == []
        assert len(transport.abort_calls) == 1
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_double_press_is_rejected_without_second_capture() -> None:
    controller, _, transport = _controller(_speech_frames())
    try:
        await _connect(controller)
        await controller.start_push_to_talk(True)
        await controller.wait_for_state(
            lambda state: state.audio.status is AssistantAudioStatus.RECORDING
        )
        await controller.start_push_to_talk(True)
        assert controller.state.error is not None
        assert controller.state.error.code == "push_to_talk_busy"
        assert len(transport.listen_start_calls) == 1
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_disable_cancels_capture_and_releases_microphone() -> None:
    controller, _, transport = _controller(_speech_frames())
    await _connect(controller)
    await controller.start_push_to_talk(True)
    await controller.wait_for_state(
        lambda state: state.audio.status is AssistantAudioStatus.RECORDING
    )
    await controller.disable_assistant()
    await controller.shutdown()

    assert controller.closed is True
    assert controller.audio_uplink_running is False
    assert controller.audio_worker_alive is False
    assert controller.microphone_lease_generation is None
    assert transport.abort_calls


@pytest.mark.asyncio
async def test_abnormal_close_during_capture_cancels_audio_before_recovery() -> None:
    controller, _, transport = _controller(_speech_frames())
    try:
        await _connect(controller)
        await controller.start_push_to_talk(True)
        await controller.wait_for_state(
            lambda state: state.audio.status is AssistantAudioStatus.RECORDING
        )
        await transport.emit_server_close(code=1006, reason="gate3_2_capture_close")
        await controller.wait_for_state(
            lambda state: not controller.audio_capture_active
            and not controller.audio_worker_alive
            and controller.microphone_lease_generation is None,
            timeout_seconds=2.0,
        )
        assert controller.audio_uplink_running is False
        assert controller.state.audio.status is AssistantAudioStatus.IDLE
    finally:
        await controller.shutdown()
