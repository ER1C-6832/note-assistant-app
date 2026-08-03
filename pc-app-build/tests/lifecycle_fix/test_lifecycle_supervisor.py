from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from app.assistant import lifecycle_supervisor as lifecycle
from app.assistant.state import (
    AssistantConnectionStatus,
    AssistantPhase,
    AssistantState,
    ConnectionState,
)


class FakeController:
    def __init__(self, state: AssistantState) -> None:
        self._state = state
        self._listeners = set()
        self.reconnect_calls: list[tuple[str, str | None]] = []

    @property
    def state(self) -> AssistantState:
        return self._state

    def subscribe(self, listener):
        self._listeners.add(listener)

        def unsubscribe() -> None:
            self._listeners.discard(listener)

        return unsubscribe

    def set_state(self, state: AssistantState) -> None:
        self._state = state
        for listener in tuple(self._listeners):
            listener(state)

    async def reconnect(
        self,
        *,
        reason: str = "manual_reconnect",
        message: str | None = None,
    ) -> None:
        self.reconnect_calls.append((reason, message))


def connected_state() -> AssistantState:
    base = AssistantState.disabled(now_ns=1)
    return replace(
        base,
        enabled=True,
        phase=AssistantPhase.CONNECTED,
        connection=ConnectionState(
            status=AssistantConnectionStatus.CONNECTED,
            session_id="session-1",
            connection_generation=1,
        ),
    )


@pytest.mark.asyncio
async def test_text_turn_timeout_auto_recovers(monkeypatch) -> None:
    monkeypatch.setattr(lifecycle, "TEXT_TURN_TIMEOUT_SECONDS", 0.02)
    state = connected_state()
    state = replace(
        state,
        phase=AssistantPhase.THINKING,
        conversation=replace(
            state.conversation,
            text_turn_counter=1,
            active_text_turn_token=1,
            active_text_turn_started_at_ns=1,
        ),
    )
    controller = FakeController(state)
    supervisor = lifecycle.SessionLifecycleSupervisor(controller)
    controller.set_state(state)
    await asyncio.sleep(0.06)
    assert controller.reconnect_calls
    assert controller.reconnect_calls[0][0] == "text_lifecycle_timeout"
    await supervisor.close()


@pytest.mark.asyncio
async def test_normal_completion_cancels_watchdog(monkeypatch) -> None:
    monkeypatch.setattr(lifecycle, "TEXT_TURN_TIMEOUT_SECONDS", 0.03)
    state = connected_state()
    busy = replace(
        state,
        phase=AssistantPhase.THINKING,
        conversation=replace(
            state.conversation,
            text_turn_counter=1,
            active_text_turn_token=1,
            active_text_turn_started_at_ns=1,
        ),
    )
    controller = FakeController(busy)
    supervisor = lifecycle.SessionLifecycleSupervisor(controller)
    controller.set_state(busy)
    controller.set_state(state)
    await asyncio.sleep(0.07)
    assert controller.reconnect_calls == []
    assert not supervisor.watchdog_running
    await supervisor.close()


@pytest.mark.asyncio
async def test_local_confirmation_checks_stuck_voice_turn(monkeypatch) -> None:
    monkeypatch.setattr(lifecycle, "LOCAL_CONFIRMATION_GRACE_SECONDS", 0.01)
    state = connected_state()
    busy = replace(
        state,
        phase=AssistantPhase.THINKING,
        conversation=replace(
            state.conversation,
            voice_turn_counter=1,
            active_voice_turn_token=1,
            active_voice_turn_started_at_ns=1,
        ),
    )
    controller = FakeController(busy)
    supervisor = lifecycle.SessionLifecycleSupervisor(controller)
    await supervisor.local_confirmation_finished(
        "confirm", "confirmation-1", "success", "已删除"
    )
    await asyncio.sleep(0.05)
    assert controller.reconnect_calls
    assert controller.reconnect_calls[0][0] == "local_confirmation_lifecycle_stuck"
    await supervisor.close()
