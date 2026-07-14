"""Deterministic Fake transport that drives the real Runtime event pump."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass

from ..events import (
    AssistantEvent,
    AssistantTextReceived,
    ClientHelloSent,
    ServerHelloReceived,
    TransportClosed,
    TransportFailed,
    TransportOpened,
)
from .fake_clock import FakeClock

EventSink = Callable[[AssistantEvent], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class OpenSucceeded:
    session_id: str = "fake-session-1"
    delay_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class OpenFailed:
    message: str = "scripted open failure"
    delay_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class TextReply:
    text: str
    delay_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class TextFailed:
    message: str = "scripted text failure"
    delay_seconds: float = 0.0


OpenStep = OpenSucceeded | OpenFailed
TextStep = TextReply | TextFailed


class ScriptedFakeTransport:
    """Consume scripted open/text outcomes while recording every adapter call."""

    def __init__(
        self,
        *,
        clock: FakeClock | None = None,
        open_steps: Iterable[OpenStep] = (),
        text_steps: Iterable[TextStep] = (),
        open_gate: asyncio.Event | None = None,
        text_gate: asyncio.Event | None = None,
    ) -> None:
        self.clock = clock or FakeClock()
        self.open_steps = deque(open_steps)
        self.text_steps = deque(text_steps)
        self.open_gate = open_gate
        self.text_gate = text_gate

        self.open_calls: list[int] = []
        self.close_calls: list[tuple[int, str]] = []
        self.sent_texts: list[tuple[int, str]] = []
        self.cancelled_open_count = 0
        self.cancelled_text_count = 0
        self.active_generation: int | None = None
        self.is_open = False
        self._event_sink: EventSink | None = None

    async def open(self, generation: int, event_sink: EventSink) -> None:
        self.open_calls.append(generation)
        self._event_sink = event_sink
        step = self.open_steps.popleft() if self.open_steps else OpenSucceeded()
        try:
            await self._wait(self.open_gate, step.delay_seconds)
        except asyncio.CancelledError:
            self.cancelled_open_count += 1
            raise

        if isinstance(step, OpenFailed):
            await event_sink(
                TransportFailed(
                    at_ns=self.clock.now_ns(),
                    generation=generation,
                    message=step.message,
                )
            )
            return

        self.active_generation = generation
        self.is_open = True
        await event_sink(TransportOpened(at_ns=self.clock.now_ns(), generation=generation))
        self.clock.advance_ns(1)
        await event_sink(ClientHelloSent(at_ns=self.clock.now_ns(), generation=generation))
        self.clock.advance_ns(1)
        await event_sink(
            ServerHelloReceived(
                at_ns=self.clock.now_ns(),
                generation=generation,
                session_id=step.session_id,
            )
        )

    async def send_text(
        self,
        generation: int,
        text: str,
        event_sink: EventSink,
    ) -> None:
        self.sent_texts.append((generation, text))
        if not self.is_open or self.active_generation != generation:
            await event_sink(
                TransportFailed(
                    at_ns=self.clock.now_ns(),
                    generation=generation,
                    message="scripted transport is not open for this generation",
                )
            )
            return

        step = self.text_steps.popleft() if self.text_steps else TextReply(f"Fake: {text}")
        try:
            await self._wait(self.text_gate, step.delay_seconds)
        except asyncio.CancelledError:
            self.cancelled_text_count += 1
            raise

        if isinstance(step, TextFailed):
            await event_sink(
                TransportFailed(
                    at_ns=self.clock.now_ns(),
                    generation=generation,
                    message=step.message,
                )
            )
            return

        await event_sink(
            AssistantTextReceived(
                at_ns=self.clock.now_ns(),
                generation=generation,
                text=step.text,
            )
        )

    async def close(
        self,
        generation: int,
        reason: str,
        event_sink: EventSink,
    ) -> None:
        self.close_calls.append((generation, reason))
        if self.active_generation == generation:
            self.active_generation = None
            self.is_open = False
        await event_sink(
            TransportClosed(
                at_ns=self.clock.now_ns(),
                generation=generation,
                code=1000,
                reason=reason,
                expected=True,
            )
        )

    async def emit_server_close(
        self,
        *,
        code: int = 1006,
        reason: str = "scripted_server_close",
    ) -> None:
        if self._event_sink is None or self.active_generation is None:
            raise RuntimeError("scripted transport has not been opened")
        generation = self.active_generation
        self.active_generation = None
        self.is_open = False
        await self._event_sink(
            TransportClosed(
                at_ns=self.clock.now_ns(),
                generation=generation,
                code=code,
                reason=reason,
                expected=False,
            )
        )

    @staticmethod
    async def _wait(gate: asyncio.Event | None, delay_seconds: float) -> None:
        if gate is not None:
            await gate.wait()
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)
