from __future__ import annotations

import asyncio

import pytest

from app.assistant import AssistantController, AssistantPhase
from app.assistant.testing import FakeClock, ScriptedFakeTransport, TextReply


@pytest.mark.asyncio
async def test_fake_text_turn_uses_token_and_completes_through_event_pump() -> None:
    clock = FakeClock()
    fake = ScriptedFakeTransport(clock=clock, text_steps=[TextReply("Fake 文本回复")])
    controller = AssistantController(transport=fake, clock=clock)

    try:
        await controller.enable_assistant()
        await controller.use_fake_runtime()
        await controller.connect()
        await controller.wait_for_state(lambda state: state.is_connected)
        await controller.send_text("Fake 输入")
        state = await controller.wait_for_state(
            lambda snapshot: snapshot.conversation.last_completed_text_turn_token == 1
        )

        assert state.phase is AssistantPhase.CONNECTED
        assert state.conversation.last_user_text == "Fake 输入"
        assert state.conversation.last_assistant_text == "Fake 文本回复"
        assert state.conversation.active_text_turn_token is None
        assert fake.sent_turns == [(state.connection.connection_generation, 1, "Fake 输入")]
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_controller_rejects_fast_second_text_while_first_is_blocked() -> None:
    gate = asyncio.Event()
    fake = ScriptedFakeTransport(text_gate=gate, text_steps=[TextReply("first")])
    controller = AssistantController(transport=fake)

    try:
        await controller.enable_assistant()
        await controller.use_fake_runtime()
        await controller.connect()
        await controller.wait_for_state(lambda state: state.is_connected)
        await controller.send_text("first")
        await controller.send_text("second")
        assert controller.state.error is not None
        assert controller.state.error.code == "text_turn_in_progress"
        assert controller.state.conversation.active_text_turn_token == 1
    finally:
        gate.set()
        await controller.shutdown()
