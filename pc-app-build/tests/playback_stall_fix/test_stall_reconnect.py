from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from app.assistant import lifecycle_supervisor as lifecycle
from app.assistant.state import (
    AssistantAudioStatus,
    AssistantConnectionStatus,
    AssistantError,
    AssistantErrorCategory,
    AssistantPhase,
    AssistantState,
    ConnectionState,
)


class _Controller:
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


def _connected_state() -> AssistantState:
    base = AssistantState.disabled(now_ns=1)
    return replace(
        base,
        enabled=True,
        phase=AssistantPhase.CONNECTED,
        connection=ConnectionState(
            status=AssistantConnectionStatus.CONNECTED,
            session_id="session",
            connection_generation=3,
        ),
    )


@pytest.mark.asyncio
async def test_playback_stall_error_automatically_reconnects(monkeypatch) -> None:
    monkeypatch.setattr(lifecycle, "PLAYBACK_STALL_RECOVERY_DELAY_SECONDS", 0.01)
    state = _connected_state()
    failed = replace(
        state,
        phase=AssistantPhase.ERROR,
        audio=replace(
            state.audio,
            status=AssistantAudioStatus.ERROR,
            playback_generation=7,
            last_audio_summary="playback_failed code=playback_packet_idle_timeout",
        ),
        error=AssistantError(
            code="playback_packet_idle_timeout",
            message="no binary audio",
            category=AssistantErrorCategory.AUDIO,
            recoverable=True,
            source_event="RuntimePlaybackFailed",
            occurred_at_ns=2,
        ),
    )
    controller = _Controller(failed)
    supervisor = lifecycle.SessionLifecycleSupervisor(controller)
    controller.set_state(failed)
    await asyncio.sleep(0.05)
    assert controller.reconnect_calls == [
        (
            "playback_packet_idle_timeout",
            "语音播放链路未正常结束，正在自动恢复连接",
        )
    ]
    await supervisor.close()


@pytest.mark.asyncio
async def test_unrelated_error_does_not_force_reconnect(monkeypatch) -> None:
    monkeypatch.setattr(lifecycle, "PLAYBACK_STALL_RECOVERY_DELAY_SECONDS", 0.01)
    state = _connected_state()
    failed = replace(
        state,
        phase=AssistantPhase.ERROR,
        error=AssistantError(
            code="output_device_unavailable",
            message="no device",
            category=AssistantErrorCategory.AUDIO,
            recoverable=True,
            source_event="RuntimePlaybackFailed",
            occurred_at_ns=2,
        ),
    )
    controller = _Controller(failed)
    supervisor = lifecycle.SessionLifecycleSupervisor(controller)
    controller.set_state(failed)
    await asyncio.sleep(0.05)
    assert controller.reconnect_calls == []
    await supervisor.close()
