"""Deterministic Fake transport that drives the real Runtime event pump."""

from __future__ import annotations

import asyncio
import json
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
from ..protocol import AssistantText, ServerHello, XiaozhiMessageBuilder, XiaozhiMessageRouter
from ..state import AssistantRuntimeMode
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
    """Consume scripted outcomes while sharing the production Builder and Router."""

    def __init__(
        self,
        *,
        clock: FakeClock | None = None,
        open_steps: Iterable[OpenStep] = (),
        text_steps: Iterable[TextStep] = (),
        open_gate: asyncio.Event | None = None,
        text_gate: asyncio.Event | None = None,
        message_builder: XiaozhiMessageBuilder | None = None,
        message_router: XiaozhiMessageRouter | None = None,
    ) -> None:
        self.clock = clock or FakeClock()
        self.open_steps = deque(open_steps)
        self.text_steps = deque(text_steps)
        self.open_gate = open_gate
        self.text_gate = text_gate
        self.message_builder = message_builder or XiaozhiMessageBuilder()
        self.message_router = message_router or XiaozhiMessageRouter()

        self.open_calls: list[int] = []
        self.open_modes: list[AssistantRuntimeMode] = []
        self.close_calls: list[tuple[int, str]] = []
        self.sent_texts: list[tuple[int, str]] = []
        self.cancelled_open_count = 0
        self.cancelled_text_count = 0
        self.active_generation: int | None = None
        self.is_open = False
        self.session_id: str | None = None
        self._event_sink: EventSink | None = None

    async def open(
        self,
        generation: int,
        runtime_mode: AssistantRuntimeMode,
        event_sink: EventSink,
    ) -> None:
        self.open_calls.append(generation)
        self.open_modes.append(runtime_mode)
        self._event_sink = event_sink
        if runtime_mode is not AssistantRuntimeMode.FAKE:
            await event_sink(
                TransportFailed(
                    at_ns=self.clock.now_ns(),
                    generation=generation,
                    message="ScriptedFakeTransport 只接受 fake runtime mode",
                )
            )
            return

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
        await event_sink(
            TransportOpened(
                at_ns=self.clock.now_ns(),
                generation=generation,
                websocket_url_public="scripted://fake-runtime",
            )
        )
        self.clock.advance_ns(1)

        hello_json = self.message_builder.hello()
        await event_sink(
            ClientHelloSent(
                at_ns=self.clock.now_ns(),
                generation=generation,
                raw_json_redacted=hello_json,
            )
        )
        self.clock.advance_ns(1)

        server_json = json.dumps(
            {
                "type": "hello",
                "transport": "websocket",
                "session_id": step.session_id,
            },
            separators=(",", ":"),
        )
        routed = self.message_router.route_text(server_json)
        assert isinstance(routed, ServerHello)
        self.session_id = routed.session_id or None
        await event_sink(
            ServerHelloReceived(
                at_ns=self.clock.now_ns(),
                generation=generation,
                session_id=routed.session_id,
                transport=routed.transport,
                raw_json_redacted=routed.raw_json_redacted,
            )
        )

    async def send_text(
        self,
        generation: int,
        text: str,
        event_sink: EventSink,
    ) -> None:
        self.sent_texts.append((generation, text))
        if not self.is_open or self.active_generation != generation or not self.session_id:
            await event_sink(
                TransportFailed(
                    at_ns=self.clock.now_ns(),
                    generation=generation,
                    message="scripted transport is not open for this generation",
                )
            )
            return

        # Build the same client payload used by Real before producing a scripted server reply.
        self.message_builder.listen_detect(self.session_id, text)
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

        reply_json = json.dumps(
            {
                "session_id": self.session_id,
                "type": "text",
                "text": step.text,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        routed = self.message_router.route_text(reply_json)
        assert isinstance(routed, AssistantText)
        await event_sink(
            AssistantTextReceived(
                at_ns=self.clock.now_ns(),
                generation=generation,
                text=routed.text,
                source_type=routed.source_type,
                session_id=routed.session_id,
                raw_json_redacted=routed.raw_json_redacted,
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
            self.session_id = None
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
        self.session_id = None
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
