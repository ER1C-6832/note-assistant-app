from __future__ import annotations

import asyncio

import pytest

from app.assistant import (
    AssistantCapability,
    AssistantController,
    AssistantPhase,
    AssistantRuntimeMode,
    CapabilityStatus,
    ControllerClosedError,
)
from app.assistant.testing import FakeClock, OpenSucceeded, ScriptedFakeTransport, TextReply


@pytest.mark.asyncio
async def test_scripted_fake_transport_runs_through_single_event_pump() -> None:
    clock = FakeClock()
    transport = ScriptedFakeTransport(
        clock=clock,
        open_steps=[OpenSucceeded(session_id="gate2-session")],
        text_steps=[TextReply("Gate 2.1 fake reply")],
    )
    controller = AssistantController(transport=transport, clock=clock)
    snapshots = []
    controller.subscribe(snapshots.append)

    try:
        await controller.enable_assistant()
        await controller.use_fake_runtime()
        await controller.connect()
        connected = await controller.wait_for_state(lambda state: state.is_connected)

        assert connected.runtime_mode is AssistantRuntimeMode.FAKE
        assert connected.connection.session_id == "gate2-session"
        assert transport.open_calls == [connected.connection.connection_generation]
        assert controller.event_queue_capacity == 256
        assert controller.event_pump_running is True

        await controller.send_text("你好")
        replied = await controller.wait_for_state(
            lambda state: state.conversation.last_assistant_text == "Gate 2.1 fake reply"
        )

        assert replied.phase is AssistantPhase.CONNECTED
        assert replied.conversation.last_user_text == "你好"
        assert transport.sent_texts == [(replied.connection.connection_generation, "你好")]
        assert any(state.phase is AssistantPhase.THINKING for state in snapshots)
        assert (
            replied.capability_status(AssistantCapability.PUSH_TO_TALK) is CapabilityStatus.ACTIVE
        )
    finally:
        await controller.shutdown()

    assert controller.closed is True
    assert controller.event_pump_running is False
    assert controller.pending_effect_count == 0


@pytest.mark.asyncio
async def test_disable_cancels_blocked_open_and_late_hello_cannot_revive_state() -> None:
    clock = FakeClock()
    open_gate = asyncio.Event()
    transport = ScriptedFakeTransport(clock=clock, open_gate=open_gate)
    controller = AssistantController(transport=transport, clock=clock)

    try:
        await controller.enable_assistant()
        await controller.use_fake_runtime()
        await controller.connect()
        await asyncio.sleep(0)
        assert controller.state.phase is AssistantPhase.CONNECTING
        old_generation = controller.state.connection.connection_generation

        await controller.disable_assistant()
        assert controller.state.phase is AssistantPhase.DISABLED
        assert controller.state.connection.connection_generation == old_generation + 1
        assert transport.cancelled_open_count == 1
        assert controller.pending_effect_count == 0

        open_gate.set()
        await asyncio.sleep(0)
        assert controller.state.phase is AssistantPhase.DISABLED
        assert controller.state.connection.session_id is None
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_disable_cancels_blocked_text_effect() -> None:
    clock = FakeClock()
    text_gate = asyncio.Event()
    transport = ScriptedFakeTransport(clock=clock, text_gate=text_gate)
    controller = AssistantController(transport=transport, clock=clock)

    try:
        await controller.enable_assistant()
        await controller.use_fake_runtime()
        await controller.connect()
        await controller.wait_for_state(lambda state: state.is_connected)

        await controller.send_text("需要取消的文本")
        await asyncio.sleep(0)
        assert controller.state.phase is AssistantPhase.THINKING

        await controller.disable_assistant()
        assert transport.cancelled_text_count == 1
        assert controller.state.phase is AssistantPhase.DISABLED
        assert controller.pending_effect_count == 0
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_transport_adapter_rejects_a_runtime_mode_mismatch() -> None:
    clock = FakeClock()
    transport = ScriptedFakeTransport(clock=clock)
    controller = AssistantController(transport=transport, clock=clock)

    try:
        await controller.enable_assistant()
        await controller.connect()
        failed = await controller.wait_for_state(
            lambda state: state.error is not None and state.error.code == "transport_failure"
        )

        assert failed.phase is AssistantPhase.ERROR
        assert transport.open_calls == [1]
        assert transport.open_modes == [AssistantRuntimeMode.REAL]
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_commands_are_rejected_after_shutdown() -> None:
    clock = FakeClock()
    controller = AssistantController(
        transport=ScriptedFakeTransport(clock=clock),
        clock=clock,
    )

    await controller.shutdown()

    with pytest.raises(ControllerClosedError):
        await controller.enable_assistant()


@pytest.mark.asyncio
async def test_empty_session_error_is_not_cleared_by_expected_close_callback() -> None:
    clock = FakeClock()
    transport = ScriptedFakeTransport(
        clock=clock,
        open_steps=[OpenSucceeded(session_id="")],
    )
    controller = AssistantController(transport=transport, clock=clock)

    try:
        await controller.enable_assistant()
        await controller.use_fake_runtime()
        await controller.connect()
        state = await controller.wait_for_state(
            lambda snapshot: snapshot.error is not None
            and snapshot.error.code == "hello_missing_session_id"
        )
        await asyncio.sleep(0)

        assert state.phase is AssistantPhase.ERROR
        assert controller.state.error is not None
        assert controller.state.error.code == "hello_missing_session_id"
        assert transport.close_calls[-1][1] == "hello_missing_session_id"
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_enable_is_idempotent_while_connected() -> None:
    clock = FakeClock()
    transport = ScriptedFakeTransport(clock=clock)
    controller = AssistantController(transport=transport, clock=clock)

    try:
        await controller.enable_assistant()
        await controller.use_fake_runtime()
        await controller.connect()
        connected = await controller.wait_for_state(lambda state: state.is_connected)
        generation = connected.connection.connection_generation

        await controller.enable_assistant()

        assert controller.state.is_connected is True
        assert controller.state.connection.connection_generation == generation
        assert transport.close_calls == []
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_second_text_is_rejected_without_starting_a_parallel_turn() -> None:
    clock = FakeClock()
    text_gate = asyncio.Event()
    transport = ScriptedFakeTransport(clock=clock, text_gate=text_gate)
    controller = AssistantController(transport=transport, clock=clock)

    try:
        await controller.enable_assistant()
        await controller.use_fake_runtime()
        await controller.connect()
        await controller.wait_for_state(lambda state: state.is_connected)

        await controller.send_text("第一条")
        await asyncio.sleep(0)
        await controller.send_text("第二条")

        assert controller.state.phase is AssistantPhase.THINKING
        assert controller.state.error is not None
        assert controller.state.error.code == "text_turn_in_progress"
        assert [text for _, text in transport.sent_texts] == ["第一条"]

        text_gate.set()
        completed = await controller.wait_for_state(
            lambda state: state.conversation.last_assistant_text == "Fake: 第一条"
        )
        assert completed.phase is AssistantPhase.CONNECTED
        assert completed.error is None
    finally:
        await controller.shutdown()
