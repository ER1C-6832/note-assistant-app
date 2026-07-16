from __future__ import annotations

import asyncio
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
from app.assistant.testing import (
    FakeClock,
    OpenSucceeded,
    ScriptedFakeTransport,
    VoiceReply,
)


def _frames(count: int, sample: int = 1400) -> tuple[bytes, ...]:
    payload = struct.pack("<320h", *([sample] * 320))
    return tuple(payload for _ in range(count))


class _BlockingStopTransport(ScriptedFakeTransport):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.stop_listening_entered = asyncio.Event()
        self.release_stop_listening = asyncio.Event()

    async def stop_listening(
        self,
        generation: int,
        turn_token: int,
        capture_generation: int,
        event_sink,
    ) -> None:
        self.stop_listening_entered.set()
        await self.release_stop_listening.wait()
        await super().stop_listening(
            generation,
            turn_token,
            capture_generation,
            event_sink,
        )


def _controller(
    *,
    states,
    frames,
    replies=(),
    opens=None,
    transport_type=ScriptedFakeTransport,
):
    clock = FakeClock()
    capture = ScriptedFakeAudioCapture(FakeCaptureScript.from_frames(frames))
    engine = AssistantAudioEngine(
        capture=capture,
        encoder_factory=FakeOpusEncoder,
        vad_factory=lambda _timeout: ScriptedVoiceActivityDetector(states),
    )
    transport = transport_type(
        clock=clock,
        open_steps=opens or (OpenSucceeded(session_id="gate3-4-session"),),
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


def _assert_audio_resources_released(controller: AssistantController) -> None:
    assert controller.streaming_response_timer_running is False
    assert controller.audio_uplink_running is False
    assert controller.streaming_vad_running is False
    assert controller.audio_capture_active is False
    assert controller.audio_worker_alive is False
    assert controller.microphone_lease_generation is None


@pytest.mark.asyncio
async def test_waiting_for_next_turn_keeps_session_but_never_auto_restarts_capture() -> None:
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
        await controller.start_streaming_conversation(True)
        await controller.wait_for_state(
            lambda state: state.audio.status is AssistantAudioStatus.RECORDING
        )
        capture.emit_all()
        waiting = await controller.wait_for_state(
            lambda state: state.conversation.streaming_state
            is StreamingConversationState.WAITING_FOR_NEXT_TURN
            and state.conversation.last_assistant_text == "好的",
            timeout_seconds=3.0,
        )

        assert waiting.conversation.streaming_session_active is True
        assert waiting.audio.status is AssistantAudioStatus.IDLE
        _assert_audio_resources_released(controller)
        assert len(transport.listen_start_calls) == 1
        assert len(transport.listen_stop_calls) == 1

        await asyncio.sleep(0.05)
        assert len(transport.listen_start_calls) == 1
        assert controller.audio_capture_active is False

        await controller.stop_streaming_conversation("gate3_4_manual_stop")
        stopped = await controller.wait_for_state(
            lambda state: not state.conversation.streaming_session_active
        )
        assert stopped.phase is AssistantPhase.CONNECTED
        _assert_audio_resources_released(controller)
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_end_of_speech_then_manual_stop_sends_only_one_turn_finalizer() -> None:
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
        transport_type=_BlockingStopTransport,
    )
    assert isinstance(transport, _BlockingStopTransport)
    try:
        await _connect_streaming(controller)
        await controller.start_streaming_conversation(True)
        await controller.wait_for_state(
            lambda state: state.audio.status is AssistantAudioStatus.RECORDING
        )

        capture.emit_all()
        await asyncio.wait_for(transport.stop_listening_entered.wait(), timeout=1.0)

        # The VAD-finalize effect owns the audio lock here. Queue a session stop
        # before releasing it to deterministically exercise the competing order.
        await controller.stop_streaming_conversation("gate3_4_user_stop_after_eos")
        transport.release_stop_listening.set()

        await controller.wait_for_state(
            lambda state: not state.conversation.streaming_session_active,
            timeout_seconds=3.0,
        )
        await asyncio.sleep(0)

        assert len(transport.listen_stop_calls) == 1
        assert transport.abort_calls == []
        assert len(transport.listen_start_calls) == 1
        _assert_audio_resources_released(controller)
    finally:
        transport.release_stop_listening.set()
        await controller.shutdown()


@pytest.mark.asyncio
async def test_repeated_streaming_start_does_not_create_a_second_capture() -> None:
    states = (VoiceActivityState.WARMUP, VoiceActivityState.WAITING_FOR_SPEECH)
    controller, _, transport = _controller(states=states, frames=_frames(len(states), 0))
    try:
        await _connect_streaming(controller)
        await controller.start_streaming_conversation(True)
        await controller.wait_for_state(
            lambda state: state.audio.status is AssistantAudioStatus.RECORDING
        )
        await controller.start_streaming_conversation(True)
        await asyncio.sleep(0)

        assert len(transport.listen_start_calls) == 1
        assert controller.audio_capture_active is True

        await controller.stop_streaming_conversation("gate3_4_duplicate_start_cleanup")
        await controller.wait_for_state(
            lambda state: not state.conversation.streaming_session_active
        )
        assert len(transport.abort_calls) == 1
        _assert_audio_resources_released(controller)
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "states",
    (
        (VoiceActivityState.WARMUP, VoiceActivityState.WAITING_FOR_SPEECH),
        (
            VoiceActivityState.WARMUP,
            VoiceActivityState.WAITING_FOR_SPEECH,
            VoiceActivityState.SPEECH_DETECTED,
            VoiceActivityState.SPEECH_ACTIVE,
        ),
    ),
)
async def test_manual_stop_during_listening_or_speaking_is_single_and_leak_free(
    states,
) -> None:
    controller, capture, transport = _controller(states=states, frames=_frames(len(states)))
    try:
        await _connect_streaming(controller)
        await controller.start_streaming_conversation(True)
        await controller.wait_for_state(
            lambda state: state.audio.status is AssistantAudioStatus.RECORDING
        )
        capture.emit_all()
        await controller.stop_streaming_conversation("gate3_4_user_stop")
        await controller.wait_for_state(
            lambda state: not state.conversation.streaming_session_active
        )

        assert transport.listen_stop_calls == []
        assert len(transport.abort_calls) == 1
        _assert_audio_resources_released(controller)
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_disable_and_shutdown_leave_no_assistant_tasks_or_audio_resources() -> None:
    states = (VoiceActivityState.WARMUP, VoiceActivityState.WAITING_FOR_SPEECH)
    controller, _, _ = _controller(states=states, frames=_frames(len(states), 0))
    await _connect_streaming(controller)
    await controller.start_streaming_conversation(True)
    await controller.wait_for_state(
        lambda state: state.audio.status is AssistantAudioStatus.RECORDING
    )

    await controller.disable_assistant()
    await controller.wait_for_state(lambda state: not state.enabled)
    _assert_audio_resources_released(controller)

    await controller.shutdown()
    await asyncio.sleep(0)
    pending = [
        task.get_name()
        for task in asyncio.all_tasks()
        if task is not asyncio.current_task()
        and not task.done()
        and task.get_name().startswith("assistant-")
    ]
    assert pending == []
