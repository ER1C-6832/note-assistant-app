from __future__ import annotations

import asyncio

import pytest

from app.assistant import AssistantController, AssistantPhase, ConversationStateMachine
from app.assistant.network import ReconnectPolicy
from app.assistant.testing import OpenFailed, OpenSucceeded, ScriptedFakeTransport


def _machine(*delays: float) -> ConversationStateMachine:
    return ConversationStateMachine(
        ReconnectPolicy(
            jitter_fraction=0.0,
            backoff_seconds=(delays[0], delays[1], delays[2]),
        )
    )


@pytest.mark.asyncio
async def test_fake_abnormal_close_recovers_through_one_timer_and_new_generation() -> None:
    transport = ScriptedFakeTransport(
        open_steps=[
            OpenSucceeded(session_id="session-1"),
            OpenSucceeded(session_id="session-2"),
        ]
    )
    controller = AssistantController(
        transport=transport,
        state_machine=_machine(0.01, 0.02, 0.03),
    )

    try:
        await controller.enable_assistant()
        await controller.use_fake_runtime()
        await controller.connect()
        first = await controller.wait_for_state(lambda state: state.is_connected)
        first_generation = first.connection.connection_generation

        await transport.emit_server_close(code=1006, reason="network_lost")
        restored = await controller.wait_for_state(
            lambda state: state.is_connected
            and state.connection.connection_generation > first_generation,
            timeout_seconds=1.0,
        )

        assert restored.connection.session_id == "session-2"
        assert restored.recovery.reconnect_attempt == 0
        assert transport.open_calls == [first_generation, first_generation + 1]
        assert controller.reconnect_timer_running is False
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_disable_cancels_pending_reconnect_timer() -> None:
    transport = ScriptedFakeTransport(open_steps=[OpenSucceeded(session_id="session-1")])
    controller = AssistantController(
        transport=transport,
        state_machine=_machine(0.20, 0.20, 0.20),
    )

    try:
        await controller.enable_assistant()
        await controller.use_fake_runtime()
        await controller.connect()
        await controller.wait_for_state(lambda state: state.is_connected)
        await transport.emit_server_close(code=1006, reason="network_lost")
        await controller.wait_for_state(
            lambda state: state.phase is AssistantPhase.RECONNECTING
            and state.recovery.next_reconnect_at_ns is not None
        )
        assert controller.reconnect_timer_running is True

        await controller.disable_assistant()
        await asyncio.sleep(0.25)

        assert controller.state.phase is AssistantPhase.DISABLED
        assert controller.reconnect_timer_running is False
        assert len(transport.open_calls) == 1
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_manual_reconnect_cancels_auto_timer_without_parallel_open() -> None:
    transport = ScriptedFakeTransport(
        open_steps=[
            OpenSucceeded(session_id="session-1"),
            OpenSucceeded(session_id="manual-session"),
        ]
    )
    controller = AssistantController(
        transport=transport,
        state_machine=_machine(0.20, 0.20, 0.20),
    )

    try:
        await controller.enable_assistant()
        await controller.use_fake_runtime()
        await controller.connect()
        first = await controller.wait_for_state(lambda state: state.is_connected)
        await transport.emit_server_close(code=1006, reason="network_lost")
        await controller.wait_for_state(lambda state: state.phase is AssistantPhase.RECONNECTING)

        await controller.reconnect()
        restored = await controller.wait_for_state(
            lambda state: state.is_connected
            and state.connection.connection_generation > first.connection.connection_generation
        )
        await asyncio.sleep(0.25)

        assert restored.connection.session_id == "manual-session"
        assert controller.reconnect_timer_running is False
        assert len(transport.open_calls) == 2
    finally:
        await controller.shutdown()


class HangingCloseTransport(ScriptedFakeTransport):
    async def close(self, generation, reason, event_sink) -> None:  # type: ignore[no-untyped-def]
        await asyncio.Event().wait()


@pytest.mark.asyncio
async def test_shutdown_is_bounded_and_leaves_no_runtime_tasks() -> None:
    transport = HangingCloseTransport(open_steps=[OpenSucceeded(session_id="session-1")])
    controller = AssistantController(transport=transport)
    controller.CLOSE_EFFECT_TIMEOUT_SECONDS = 0.03
    controller.SHUTDOWN_TIMEOUT_SECONDS = 0.15

    await controller.enable_assistant()
    await controller.use_fake_runtime()
    await controller.connect()
    await controller.wait_for_state(lambda state: state.is_connected)

    await asyncio.wait_for(controller.shutdown(), timeout=0.5)

    assert controller.closed is True
    assert controller.event_pump_running is False
    assert controller.reconnect_timer_running is False
    assert controller.pending_effect_count == 0


@pytest.mark.asyncio
async def test_manual_connect_during_auto_wait_cancels_timer_and_reuses_no_old_owner() -> None:
    transport = ScriptedFakeTransport(
        open_steps=[
            OpenSucceeded(session_id="session-1"),
            OpenSucceeded(session_id="manual-connect-session"),
        ]
    )
    controller = AssistantController(
        transport=transport,
        state_machine=_machine(0.20, 0.20, 0.20),
    )

    try:
        await controller.enable_assistant()
        await controller.use_fake_runtime()
        await controller.connect()
        first = await controller.wait_for_state(lambda state: state.is_connected)
        await transport.emit_server_close(code=1006, reason="network_lost")
        await controller.wait_for_state(
            lambda state: state.phase is AssistantPhase.RECONNECTING
            and state.recovery.next_reconnect_at_ns is not None
        )

        await controller.connect()
        restored = await controller.wait_for_state(
            lambda state: state.is_connected
            and state.connection.connection_generation > first.connection.connection_generation
        )
        await asyncio.sleep(0.25)

        assert restored.connection.session_id == "manual-connect-session"
        assert controller.reconnect_timer_running is False
        assert len(transport.open_calls) == 2
        assert any(reason == "manual_connect" for _, reason in transport.close_calls)
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_controller_stops_after_three_automatic_retries() -> None:
    transport = ScriptedFakeTransport(
        open_steps=[
            OpenFailed(message="failure-1"),
            OpenFailed(message="failure-2"),
            OpenFailed(message="failure-3"),
            OpenFailed(message="failure-4"),
        ]
    )
    controller = AssistantController(
        transport=transport,
        state_machine=_machine(0.01, 0.01, 0.01),
    )

    try:
        await controller.enable_assistant()
        await controller.use_fake_runtime()
        await controller.connect()
        exhausted = await controller.wait_for_state(
            lambda state: state.error is not None and state.error.code == "reconnect_exhausted",
            timeout_seconds=1.0,
        )

        assert exhausted.phase is AssistantPhase.ERROR
        assert exhausted.recovery.reconnect_attempt == 3
        assert exhausted.recovery.next_reconnect_at_ns is None
        assert exhausted.recovery.runtime_error_count == 4
        assert len(transport.open_calls) == 4
        assert controller.reconnect_timer_running is False
    finally:
        await controller.shutdown()
