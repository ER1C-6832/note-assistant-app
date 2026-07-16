from __future__ import annotations

import asyncio

import pytest

from app.assistant.effects import StartStreamingConversation
from app.assistant.playback.two_turn_controller import AssistantController
from app.assistant.state import AssistantEntrySource


class _Clock:
    def __init__(self) -> None:
        self.value = 1_000_000

    def now_ns(self) -> int:
        self.value += 1_000_000
        return self.value


class _Harness(AssistantController):
    def __init__(self) -> None:
        self._clock = _Clock()
        self._auto_next_turn_keys = {}
        self._auto_next_turn_request_count = 0
        self._auto_next_turn_started_count = 0
        self._auto_next_turn_suppressed_count = 0
        self._auto_next_turn_last_latency_ms = None
        self.executed = []
        self._capture_active = False

    @property
    def audio_capture_active(self) -> bool:
        return self._capture_active

    async def _execute_effect(self, effect) -> None:
        self.executed.append(effect)
        await asyncio.sleep(0)
        self._capture_active = True


def _effect() -> StartStreamingConversation:
    return StartStreamingConversation(
        connection_generation=1,
        streaming_generation=1,
        capture_generation=2,
        turn_token=2,
        turn_index=2,
        requested_at_ns=1_000_000,
        idle_timeout_ms=8_000,
        source=AssistantEntrySource.STREAMING_BUTTON,
        session_id="streaming-session",
    )


@pytest.mark.asyncio
async def test_auto_next_effect_executes_inline_and_exactly_once() -> None:
    controller = _Harness()
    effect = _effect()

    await controller._apply_effects((effect,))
    await controller._apply_effects((effect,))

    assert controller.executed == [effect]
    assert controller.auto_next_turn_request_count == 1
    assert controller.auto_next_turn_started_count == 1
    assert controller.auto_next_turn_suppressed_count == 1
    assert controller.auto_next_turn_last_latency_ms is not None


def test_only_turn_index_after_one_uses_auto_next_path() -> None:
    first = _effect()
    first = StartStreamingConversation(
        connection_generation=first.connection_generation,
        streaming_generation=first.streaming_generation,
        capture_generation=1,
        turn_token=1,
        turn_index=1,
        requested_at_ns=first.requested_at_ns,
        idle_timeout_ms=first.idle_timeout_ms,
        source=first.source,
        session_id=first.session_id,
    )
    assert not AssistantController._is_auto_next_effect(first)
    assert AssistantController._is_auto_next_effect(_effect())
