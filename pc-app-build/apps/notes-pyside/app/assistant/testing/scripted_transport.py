"""Deterministic Fake transport that drives the real Runtime event pump."""

from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass

from ..events import (
    AbortSent,
    AssistantEvent,
    AssistantTextReceived,
    ClientHelloSent,
    ClientTextSent,
    ListenStartSent,
    ListenStopSent,
    ServerHelloReceived,
    TextTurnCompleted,
    TransportClosed,
    TransportFailed,
    TransportOpened,
    VoiceTurnCompleted,
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
    source_type: str = "text"
    delay_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class TextFailed:
    message: str = "scripted text failure"
    delay_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class VoiceReply:
    stt_text: str = "假语音命令"
    assistant_text: str = "收到"
    delay_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class VoiceFailed:
    message: str = "scripted voice failure"
    delay_seconds: float = 0.0


OpenStep = OpenSucceeded | OpenFailed
TextStep = TextReply | TextFailed
VoiceStep = VoiceReply | VoiceFailed


class ScriptedFakeTransport:
    """Consume scripted outcomes while sharing the production Builder and Router."""

    def __init__(
        self,
        *,
        clock: FakeClock | None = None,
        open_steps: Iterable[OpenStep] = (),
        text_steps: Iterable[TextStep] = (),
        voice_steps: Iterable[VoiceStep] = (),
        open_gate: asyncio.Event | None = None,
        text_gate: asyncio.Event | None = None,
        voice_gate: asyncio.Event | None = None,
        message_builder: XiaozhiMessageBuilder | None = None,
        message_router: XiaozhiMessageRouter | None = None,
    ) -> None:
        self.clock = clock or FakeClock()
        self.open_steps = deque(open_steps)
        self.text_steps = deque(text_steps)
        self.voice_steps = deque(voice_steps)
        self.open_gate = open_gate
        self.text_gate = text_gate
        self.voice_gate = voice_gate
        self.message_builder = message_builder or XiaozhiMessageBuilder()
        self.message_router = message_router or XiaozhiMessageRouter()

        self.open_calls: list[int] = []
        self.open_modes: list[AssistantRuntimeMode] = []
        self.close_calls: list[tuple[int, str]] = []
        self.sent_texts: list[tuple[int, str]] = []
        self.sent_turns: list[tuple[int, int, str]] = []
        self.listen_start_calls: list[tuple[int, int, int, str]] = []
        self.listen_stop_calls: list[tuple[int, int, int]] = []
        self.abort_calls: list[tuple[int, int, int, str]] = []
        self.sent_audio_packets: list[tuple[int, int, int, bytes]] = []
        self.cancelled_open_count = 0
        self.cancelled_text_count = 0
        self.cancelled_voice_count = 0
        self.active_generation: int | None = None
        self.active_voice_turn_token: int | None = None
        self.active_capture_generation: int | None = None
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
            await self._emit_not_open(
                generation,
                event_sink,
                "fake transport requires fake mode",
                retryable=False,
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
                    at_ns=self.clock.now_ns(), generation=generation, message=step.message
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
        hello_json = self.message_builder.hello()
        await event_sink(
            ClientHelloSent(
                at_ns=self.clock.now_ns(),
                generation=generation,
                raw_json_redacted=hello_json,
            )
        )
        server_json = json.dumps(
            {"type": "hello", "transport": "websocket", "session_id": step.session_id},
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
        turn_token: int,
        text: str,
        event_sink: EventSink,
    ) -> None:
        self.sent_texts.append((generation, text))
        self.sent_turns.append((generation, turn_token, text))
        if not self._is_ready(generation):
            await self._emit_not_open(generation, event_sink)
            return
        assert self.session_id is not None
        outgoing_json = self.message_builder.listen_detect(self.session_id, text)
        await event_sink(
            ClientTextSent(
                at_ns=self.clock.now_ns(),
                generation=generation,
                turn_token=turn_token,
                raw_json_redacted=outgoing_json,
            )
        )
        step = self.text_steps.popleft() if self.text_steps else TextReply(f"Fake: {text}")
        try:
            await self._wait(self.text_gate, step.delay_seconds)
        except asyncio.CancelledError:
            self.cancelled_text_count += 1
            raise
        if isinstance(step, TextFailed):
            await event_sink(
                TransportFailed(
                    at_ns=self.clock.now_ns(), generation=generation, message=step.message
                )
            )
            return
        await self._emit_assistant_text(
            generation=generation,
            turn_token=turn_token,
            source_type=step.source_type,
            text=step.text,
            event_sink=event_sink,
        )
        await event_sink(
            TextTurnCompleted(
                at_ns=self.clock.now_ns(),
                generation=generation,
                turn_token=turn_token,
                reason="scripted_reply_complete",
                had_assistant_text=True,
            )
        )

    async def start_listening(
        self,
        generation: int,
        turn_token: int,
        capture_generation: int,
        mode: str,
        event_sink: EventSink,
    ) -> None:
        self.listen_start_calls.append((generation, turn_token, capture_generation, mode))
        if not self._is_ready(generation):
            await self._emit_not_open(generation, event_sink)
            return
        if self.active_voice_turn_token is not None:
            raise RuntimeError("scripted voice turn is already active")
        assert self.session_id is not None
        raw = self.message_builder.start_listening(self.session_id, mode)
        self.active_voice_turn_token = turn_token
        self.active_capture_generation = capture_generation
        await event_sink(
            ListenStartSent(
                at_ns=self.clock.now_ns(),
                generation=generation,
                capture_generation=capture_generation,
                turn_token=turn_token,
                raw_json_redacted=raw,
            )
        )

    async def send_audio(
        self,
        generation: int,
        turn_token: int,
        capture_generation: int,
        payload: bytes,
        event_sink: EventSink,
    ) -> None:
        del event_sink
        if not self._voice_matches(generation, turn_token, capture_generation):
            raise RuntimeError("scripted voice turn is not active")
        self.sent_audio_packets.append((generation, turn_token, capture_generation, bytes(payload)))

    async def stop_listening(
        self,
        generation: int,
        turn_token: int,
        capture_generation: int,
        event_sink: EventSink,
    ) -> None:
        self.listen_stop_calls.append((generation, turn_token, capture_generation))
        if not self._voice_matches(generation, turn_token, capture_generation):
            return
        assert self.session_id is not None
        raw = self.message_builder.stop_listening(self.session_id)
        await event_sink(
            ListenStopSent(
                at_ns=self.clock.now_ns(),
                generation=generation,
                capture_generation=capture_generation,
                turn_token=turn_token,
                raw_json_redacted=raw,
            )
        )
        step = self.voice_steps.popleft() if self.voice_steps else VoiceReply()
        try:
            await self._wait(self.voice_gate, step.delay_seconds)
        except asyncio.CancelledError:
            self.cancelled_voice_count += 1
            raise
        if isinstance(step, VoiceFailed):
            await event_sink(
                TransportFailed(
                    at_ns=self.clock.now_ns(), generation=generation, message=step.message
                )
            )
            self._clear_voice()
            return
        await self._emit_assistant_text(
            generation=generation,
            turn_token=turn_token,
            source_type="stt",
            text=step.stt_text,
            event_sink=event_sink,
        )
        await self._emit_assistant_text(
            generation=generation,
            turn_token=turn_token,
            source_type="text",
            text=step.assistant_text,
            event_sink=event_sink,
        )
        await event_sink(
            VoiceTurnCompleted(
                at_ns=self.clock.now_ns(),
                generation=generation,
                capture_generation=capture_generation,
                turn_token=turn_token,
                reason="scripted_voice_reply_complete",
                had_stt_text=bool(step.stt_text.strip()),
                had_assistant_text=bool(step.assistant_text.strip()),
            )
        )
        self._clear_voice()

    async def abort(
        self,
        generation: int,
        turn_token: int,
        capture_generation: int,
        reason: str,
        event_sink: EventSink,
    ) -> None:
        self.abort_calls.append((generation, turn_token, capture_generation, reason))
        if not self._is_ready(generation):
            return
        assert self.session_id is not None
        raw = self.message_builder.abort(self.session_id, reason)
        await event_sink(
            AbortSent(
                at_ns=self.clock.now_ns(),
                generation=generation,
                capture_generation=capture_generation,
                turn_token=turn_token,
                reason=reason,
                raw_json_redacted=raw,
            )
        )
        await event_sink(
            VoiceTurnCompleted(
                at_ns=self.clock.now_ns(),
                generation=generation,
                capture_generation=capture_generation,
                turn_token=turn_token,
                reason=reason,
            )
        )
        self._clear_voice()

    async def close(self, generation: int, reason: str, event_sink: EventSink) -> None:
        self.close_calls.append((generation, reason))
        if self.active_generation == generation:
            self.active_generation = None
            self.is_open = False
            self.session_id = None
            self._clear_voice()
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
        self._clear_voice()
        await self._event_sink(
            TransportClosed(
                at_ns=self.clock.now_ns(),
                generation=generation,
                code=code,
                reason=reason,
                expected=False,
            )
        )

    async def _emit_assistant_text(
        self,
        *,
        generation: int,
        turn_token: int,
        source_type: str,
        text: str,
        event_sink: EventSink,
    ) -> None:
        reply_json = json.dumps(
            {"session_id": self.session_id, "type": source_type, "text": text},
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
                turn_token=turn_token,
            )
        )

    def _is_ready(self, generation: int) -> bool:
        return bool(self.is_open and self.active_generation == generation and self.session_id)

    def _voice_matches(self, generation: int, turn_token: int, capture_generation: int) -> bool:
        return bool(
            self._is_ready(generation)
            and self.active_voice_turn_token == turn_token
            and self.active_capture_generation == capture_generation
        )

    def _clear_voice(self) -> None:
        self.active_voice_turn_token = None
        self.active_capture_generation = None

    async def _emit_not_open(
        self,
        generation: int,
        event_sink: EventSink,
        message: str = "scripted transport is not open for this generation",
        *,
        retryable: bool = True,
    ) -> None:
        await event_sink(
            TransportFailed(
                at_ns=self.clock.now_ns(),
                generation=generation,
                message=message,
                retryable=retryable,
            )
        )

    @staticmethod
    async def _wait(gate: asyncio.Event | None, delay_seconds: float) -> None:
        if gate is not None:
            await gate.wait()
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)
