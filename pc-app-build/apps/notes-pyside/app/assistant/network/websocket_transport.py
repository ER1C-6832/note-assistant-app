"""Real Xiaozhi WebSocket transport with one receiver and one queued sender."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Protocol

from ..events import (
    AssistantTextReceived,
    BinaryAudioReceived,
    ClientHelloSent,
    ClientTextSent,
    ProtocolInvalidMessageReceived,
    ProtocolMessageObserved,
    ProtocolUnknownMessageReceived,
    ServerHelloReceived,
    TextTurnCompleted,
    TransportClosed,
    TransportFailed,
    TransportOpened,
    TtsStateReceived,
)
from ..protocol import (
    AssistantText,
    BinaryAudio,
    ListenState,
    McpEnvelope,
    ProtocolError,
    ServerHello,
    TtsState,
    UnknownJson,
    XiaozhiMessageBuilder,
    XiaozhiMessageRouter,
    has_readable_transcript_text,
    is_terminal_tts_state,
)
from ..state import AssistantRuntimeMode
from .transport import ConnectionConfigProvider, EventSink, WebSocketConnectionConfig

HELLO_TIMEOUT_SECONDS = 8.0
OPEN_TIMEOUT_SECONDS = 5.0
CLOSE_TIMEOUT_SECONDS = 10.0
MAX_MESSAGE_BYTES = 10 * 1024 * 1024
SEND_QUEUE_CAPACITY = 64
MAX_CLOSE_REASON_LENGTH = 80
TEXT_TURN_SETTLE_SECONDS = 1.5
TEXT_TTS_FALLBACK_SECONDS = 6.0
TEXT_TURN_RESPONSE_TIMEOUT_SECONDS = 30.0


class WebSocketClosed(RuntimeError):
    def __init__(self, code: int, reason: str) -> None:
        super().__init__(f"WebSocket closed: {code} {reason}")
        self.code = code
        self.reason = reason


class WebSocketConnection(Protocol):
    async def send(self, message: str | bytes) -> None: ...

    async def recv(self) -> str | bytes: ...

    async def close(self, *, code: int = 1000, reason: str = "") -> None: ...


class WebSocketConnector(Protocol):
    async def connect(self, config: WebSocketConnectionConfig) -> WebSocketConnection: ...


class WebsocketsConnectionAdapter:
    def __init__(self, connection) -> None:
        self._connection = connection

    async def send(self, message: str | bytes) -> None:
        await self._connection.send(message)

    async def recv(self) -> str | bytes:
        from websockets.exceptions import ConnectionClosed

        try:
            return await self._connection.recv()
        except ConnectionClosed as exc:
            raise WebSocketClosed(exc.code or 1006, exc.reason or "connection_closed") from exc

    async def close(self, *, code: int = 1000, reason: str = "") -> None:
        await self._connection.close(code=code, reason=reason)


class WebsocketsConnector:
    """Production connector using the websockets asyncio implementation."""

    async def connect(self, config: WebSocketConnectionConfig) -> WebSocketConnection:
        from websockets.asyncio.client import connect

        connection = await connect(
            config.websocket_url,
            additional_headers=config.headers(),
            open_timeout=OPEN_TIMEOUT_SECONDS,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=CLOSE_TIMEOUT_SECONDS,
            max_size=MAX_MESSAGE_BYTES,
            max_queue=16,
            write_limit=32 * 1024,
            compression=None,
            proxy=None,
        )
        return WebsocketsConnectionAdapter(connection)


@dataclass(slots=True)
class _OutboundMessage:
    payload: str | bytes
    completed: asyncio.Future[None]


@dataclass(slots=True)
class _ActiveConnection:
    generation: int
    connection: WebSocketConnection
    event_sink: EventSink
    send_queue: asyncio.Queue[_OutboundMessage | None]
    hello_received: asyncio.Event = field(default_factory=asyncio.Event)
    session_id: str | None = None
    expected_close: bool = False
    close_started: bool = False
    close_emitted: bool = False
    active_text_turn_token: int | None = None
    text_turn_had_assistant_text: bool = False
    text_turn_settle_task: asyncio.Task[None] | None = None
    text_turn_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    text_sent_ready: asyncio.Event = field(default_factory=asyncio.Event)


class RealWebSocketTransport:
    """Own one socket, one recv loop, and one bounded sender queue per generation."""

    def __init__(
        self,
        *,
        config_provider: ConnectionConfigProvider,
        clock,
        connector: WebSocketConnector | None = None,
        message_builder: XiaozhiMessageBuilder | None = None,
        message_router: XiaozhiMessageRouter | None = None,
        hello_timeout_seconds: float = HELLO_TIMEOUT_SECONDS,
    ) -> None:
        self._config_provider = config_provider
        self._clock = clock
        self._connector = connector or WebsocketsConnector()
        self._builder = message_builder or XiaozhiMessageBuilder()
        self._router = message_router or XiaozhiMessageRouter()
        self._hello_timeout_seconds = hello_timeout_seconds
        self._active: _ActiveConnection | None = None
        self._active_lock = asyncio.Lock()

    async def open(
        self,
        generation: int,
        runtime_mode: AssistantRuntimeMode,
        event_sink: EventSink,
    ) -> None:
        if runtime_mode is not AssistantRuntimeMode.REAL:
            await event_sink(
                TransportFailed(
                    at_ns=self._clock.now_ns(),
                    generation=generation,
                    message="RealWebSocketTransport 只接受 real runtime mode",
                )
            )
            return

        active: _ActiveConnection | None = None
        sender_task: asyncio.Task[None] | None = None
        receiver_task: asyncio.Task[None] | None = None
        hello_wait_task: asyncio.Task[bool] | None = None
        try:
            config = await self._config_provider.load_real()
            config.validate()
            connection = await self._connector.connect(config)
            active = _ActiveConnection(
                generation=generation,
                connection=connection,
                event_sink=event_sink,
                send_queue=asyncio.Queue(maxsize=SEND_QUEUE_CAPACITY),
            )
            async with self._active_lock:
                if self._active is not None:
                    raise RuntimeError("已有真实 WebSocket generation 正在运行")
                self._active = active

            await event_sink(
                TransportOpened(
                    at_ns=self._clock.now_ns(),
                    generation=generation,
                    websocket_url_public=config.public_url,
                )
            )

            sender_task = asyncio.create_task(
                self._sender_loop(active),
                name=f"assistant-ws-sender-{generation}",
            )

            # The client hello is fully written and recorded before the sole receiver
            # starts. This preserves the protocol ordering even with an eager test
            # server and makes "socket open" distinct from "hello/session ready".
            hello_json = self._builder.hello()
            await self._enqueue_and_wait(active, hello_json)
            await event_sink(
                ClientHelloSent(
                    at_ns=self._clock.now_ns(),
                    generation=generation,
                    raw_json_redacted=hello_json,
                )
            )

            receiver_task = asyncio.create_task(
                self._receiver_loop(active),
                name=f"assistant-ws-receiver-{generation}",
            )
            hello_wait_task = asyncio.create_task(active.hello_received.wait())
            done, _ = await asyncio.wait(
                {hello_wait_task, receiver_task},
                timeout=self._hello_timeout_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                await event_sink(
                    TransportFailed(
                        at_ns=self._clock.now_ns(),
                        generation=generation,
                        message="等待真实服务端 hello 超时",
                    )
                )
                active.expected_close = True
                await self._safe_close(active, reason="hello_timeout")
                return
            if receiver_task in done:
                await receiver_task
                return
            if not active.session_id:
                active.expected_close = True
                await self._safe_close(active, reason="hello_missing_session_id", code=1002)
                if not receiver_task.done():
                    await receiver_task
                return

            await receiver_task
        except asyncio.CancelledError:
            if active is not None:
                active.expected_close = True
                await self._safe_close(active, reason="cancelled")
            raise
        except Exception as exc:
            await event_sink(
                TransportFailed(
                    at_ns=self._clock.now_ns(),
                    generation=generation,
                    message=_safe_error_text(exc),
                )
            )
            if active is not None:
                active.expected_close = True
                await self._safe_close(active, reason="open_failed")
        finally:
            if hello_wait_task is not None:
                hello_wait_task.cancel()
            await _cancel_tasks(sender_task, receiver_task)
            if active is not None:
                await self._safe_close(active, reason="transport_cleanup")
            async with self._active_lock:
                if self._active is active:
                    self._active = None

    async def send_text(
        self,
        generation: int,
        turn_token: int,
        text: str,
        event_sink: EventSink,
    ) -> None:
        active = await self._get_active(generation)
        if active is None or not active.session_id:
            await event_sink(
                TransportFailed(
                    at_ns=self._clock.now_ns(),
                    generation=generation,
                    message="真实 WebSocket 尚未建立有效 session",
                )
            )
            return
        if turn_token <= 0:
            raise ValueError("text turn token must be positive")

        async with active.text_turn_lock:
            if active.active_text_turn_token is not None:
                raise RuntimeError("上一文本回合尚未完成，拒绝并行发送")
            active.active_text_turn_token = turn_token
            active.text_turn_had_assistant_text = False
            active.text_sent_ready.clear()
            self._cancel_text_turn_settle(active)
            payload = self._builder.listen_detect(active.session_id, text)
            try:
                await self._enqueue_and_wait(active, payload)
            except Exception:
                active.active_text_turn_token = None
                active.text_sent_ready.set()
                raise

        try:
            await event_sink(
                ClientTextSent(
                    at_ns=self._clock.now_ns(),
                    generation=generation,
                    turn_token=turn_token,
                    raw_json_redacted=payload,
                )
            )
            if active.active_text_turn_token == turn_token:
                self._schedule_text_turn_settle(
                    active,
                    delay_seconds=TEXT_TURN_RESPONSE_TIMEOUT_SECONDS,
                    reason="response_timeout",
                )
        finally:
            active.text_sent_ready.set()

    async def close(
        self,
        generation: int,
        reason: str,
        event_sink: EventSink,
    ) -> None:
        active = await self._get_active(generation)
        if active is not None:
            active.expected_close = True
            active.text_sent_ready.set()
            self._cancel_text_turn_settle(active)
            await self._safe_close(active, reason=reason)
            await self._emit_close(active, code=1000, reason=reason, expected=True)
            return
        await event_sink(
            TransportClosed(
                at_ns=self._clock.now_ns(),
                generation=generation,
                code=1000,
                reason=reason,
                expected=True,
            )
        )

    async def _sender_loop(self, active: _ActiveConnection) -> None:
        while True:
            item = await active.send_queue.get()
            try:
                if item is None:
                    return
                await active.connection.send(item.payload)
                if not item.completed.done():
                    item.completed.set_result(None)
            except Exception as exc:
                if item is not None and not item.completed.done():
                    item.completed.set_exception(exc)
                raise
            finally:
                active.send_queue.task_done()

    async def _receiver_loop(self, active: _ActiveConnection) -> None:
        try:
            while True:
                message = await active.connection.recv()
                if isinstance(message, str):
                    await self._dispatch_protocol_event(active, self._router.route_text(message))
                else:
                    await self._dispatch_protocol_event(
                        active, self._router.route_binary(bytes(message))
                    )
        except asyncio.CancelledError:
            raise
        except WebSocketClosed as exc:
            active.close_started = True
            await self._emit_close(
                active,
                code=exc.code,
                reason=exc.reason,
                expected=active.expected_close or exc.code in {1000, 1001},
            )
        except Exception as exc:
            if active.expected_close:
                await self._emit_close(active, code=1000, reason="client_close", expected=True)
                return
            await active.event_sink(
                TransportFailed(
                    at_ns=self._clock.now_ns(),
                    generation=active.generation,
                    message=_safe_error_text(exc),
                )
            )

    async def _dispatch_protocol_event(self, active: _ActiveConnection, event) -> None:
        now = self._clock.now_ns()
        if isinstance(event, ServerHello):
            active.session_id = event.session_id.strip() or None
            await active.event_sink(
                ServerHelloReceived(
                    at_ns=now,
                    generation=active.generation,
                    session_id=event.session_id,
                    transport=event.transport,
                    raw_json_redacted=event.raw_json_redacted,
                )
            )
            active.hello_received.set()
            return
        if isinstance(event, AssistantText):
            turn_token = active.active_text_turn_token
            if turn_token is not None:
                await active.text_sent_ready.wait()
            readable = has_readable_transcript_text(event.text)
            if readable and event.source_type != "stt":
                active.text_turn_had_assistant_text = True
            await active.event_sink(
                AssistantTextReceived(
                    at_ns=now,
                    generation=active.generation,
                    text=event.text,
                    source_type=event.source_type,
                    session_id=event.session_id,
                    raw_json_redacted=event.raw_json_redacted,
                    turn_token=turn_token,
                )
            )
            if readable and event.source_type != "stt":
                self._schedule_text_turn_settle(
                    active,
                    delay_seconds=TEXT_TURN_SETTLE_SECONDS,
                    reason="assistant_text_settled",
                )
            return
        if isinstance(event, TtsState):
            turn_token = active.active_text_turn_token
            if turn_token is not None:
                await active.text_sent_ready.wait()
            readable = has_readable_transcript_text(event.text)
            if readable:
                active.text_turn_had_assistant_text = True
            await active.event_sink(
                TtsStateReceived(
                    at_ns=now,
                    generation=active.generation,
                    state=event.state,
                    turn_token=turn_token,
                    text=event.text,
                    session_id=event.session_id,
                    raw_json_redacted=event.raw_json_redacted,
                )
            )
            if is_terminal_tts_state(event.state):
                await self._complete_text_turn(active, reason=f"tts_{event.state}")
            elif readable:
                self._schedule_text_turn_settle(
                    active,
                    delay_seconds=TEXT_TURN_SETTLE_SECONDS,
                    reason="tts_text_settled",
                )
            elif turn_token is not None:
                self._schedule_text_turn_settle(
                    active,
                    delay_seconds=TEXT_TTS_FALLBACK_SECONDS,
                    reason="tts_state_fallback",
                )
            return
        if isinstance(event, UnknownJson):
            await active.event_sink(
                ProtocolUnknownMessageReceived(
                    at_ns=now,
                    generation=active.generation,
                    message_type=event.message_type,
                    session_id=event.session_id,
                    raw_json_redacted=event.raw_json_redacted,
                )
            )
            return
        if isinstance(event, ProtocolError):
            await active.event_sink(
                ProtocolInvalidMessageReceived(
                    at_ns=now,
                    generation=active.generation,
                    error=event.error,
                    raw_text_redacted=event.raw_text_redacted,
                )
            )
            return
        if isinstance(event, BinaryAudio):
            await active.event_sink(
                BinaryAudioReceived(
                    at_ns=now,
                    generation=active.generation,
                    size_bytes=event.size_bytes,
                )
            )
            return
        if isinstance(event, (ListenState, McpEnvelope)):
            await active.event_sink(
                ProtocolMessageObserved(
                    at_ns=now,
                    generation=active.generation,
                    event_name=type(event).__name__,
                    message_type=_message_type(event),
                    session_id=event.session_id,
                    raw_json_redacted=event.raw_json_redacted,
                )
            )
            return
        raise TypeError(f"unsupported protocol event: {type(event).__name__}")

    def _schedule_text_turn_settle(
        self,
        active: _ActiveConnection,
        *,
        delay_seconds: float,
        reason: str,
    ) -> None:
        self._cancel_text_turn_settle(active)

        async def settle() -> None:
            try:
                await asyncio.sleep(delay_seconds)
                await self._complete_text_turn(active, reason=reason)
            except asyncio.CancelledError:
                raise

        active.text_turn_settle_task = asyncio.create_task(
            settle(),
            name=f"assistant-text-turn-settle-{active.generation}",
        )

    def _cancel_text_turn_settle(self, active: _ActiveConnection) -> None:
        task = active.text_turn_settle_task
        if task is not None and not task.done() and task is not asyncio.current_task():
            task.cancel()
        active.text_turn_settle_task = None

    async def _complete_text_turn(
        self,
        active: _ActiveConnection,
        *,
        reason: str,
    ) -> None:
        async with active.text_turn_lock:
            turn_token = active.active_text_turn_token
            if turn_token is None:
                return
            had_assistant_text = active.text_turn_had_assistant_text
            active.active_text_turn_token = None
            active.text_turn_had_assistant_text = False
            active.text_sent_ready.set()
            self._cancel_text_turn_settle(active)

        await active.event_sink(
            TextTurnCompleted(
                at_ns=self._clock.now_ns(),
                generation=active.generation,
                turn_token=turn_token,
                reason=reason,
                had_assistant_text=had_assistant_text,
            )
        )

    async def _enqueue_and_wait(self, active: _ActiveConnection, payload: str | bytes) -> None:
        future = asyncio.get_running_loop().create_future()
        await active.send_queue.put(_OutboundMessage(payload=payload, completed=future))
        await future

    async def _get_active(self, generation: int) -> _ActiveConnection | None:
        async with self._active_lock:
            active = self._active
            if active is None or active.generation != generation:
                return None
            return active

    async def _safe_close(
        self,
        active: _ActiveConnection,
        *,
        reason: str,
        code: int = 1000,
    ) -> None:
        if active.close_started:
            return
        active.close_started = True
        clean_reason = reason[:MAX_CLOSE_REASON_LENGTH]
        try:
            await active.connection.close(code=code, reason=clean_reason)
        except Exception:
            return

    async def _emit_close(
        self,
        active: _ActiveConnection,
        *,
        code: int,
        reason: str,
        expected: bool,
    ) -> None:
        if active.close_emitted:
            return
        active.close_emitted = True
        await active.event_sink(
            TransportClosed(
                at_ns=self._clock.now_ns(),
                generation=active.generation,
                code=code,
                reason=reason or "connection_closed",
                expected=expected,
            )
        )


def _message_type(event: TtsState | ListenState | McpEnvelope) -> str:
    if isinstance(event, TtsState):
        return "tts"
    if isinstance(event, ListenState):
        return "listen"
    return "mcp"


async def _cancel_tasks(*tasks: asyncio.Task[None] | None) -> None:
    live = tuple(task for task in tasks if task is not None and not task.done())
    for task in live:
        task.cancel()
    if live:
        await asyncio.gather(*live, return_exceptions=True)


_SENSITIVE_VALUE_PATTERN = re.compile(
    r"(?i)(bearer\s+)[^\s,;]+|"
    r"((?:token|authorization|hmac|secret|key)\s*[:=]\s*)[^\s,;&]+|"
    r"([?&](?:token|access_token|auth|key)=)[^&\s]+"
)


def _safe_error_text(exc: Exception) -> str:
    text = str(exc) or type(exc).__name__

    def replace_sensitive(match: re.Match[str]) -> str:
        prefix = match.group(1) or match.group(2) or match.group(3) or ""
        return f"{prefix}***"

    redacted = _SENSITIVE_VALUE_PATTERN.sub(replace_sensitive, text)
    return f"{type(exc).__name__}: {redacted[:240]}"
