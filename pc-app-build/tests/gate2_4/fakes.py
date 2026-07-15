from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.assistant.network import WebSocketClosed, WebSocketConnectionConfig


class StaticConfigProvider:
    def __init__(self, config: WebSocketConnectionConfig) -> None:
        self.config = config
        self.calls = 0

    async def load_real(self) -> WebSocketConnectionConfig:
        self.calls += 1
        return self.config


class ScriptedWebSocketConnection:
    def __init__(self, messages=()) -> None:
        self.incoming: asyncio.Queue[str | bytes | BaseException] = asyncio.Queue()
        for message in messages:
            self.incoming.put_nowait(message)
        self.sent: list[str | bytes] = []
        self.close_calls: list[tuple[int, str]] = []
        self.send_gate: asyncio.Event | None = None
        self.active_sends = 0
        self.max_concurrent_sends = 0
        self.closed = False

    async def send(self, message: str | bytes) -> None:
        self.active_sends += 1
        self.max_concurrent_sends = max(self.max_concurrent_sends, self.active_sends)
        try:
            if self.send_gate is not None:
                await self.send_gate.wait()
            await asyncio.sleep(0)
            self.sent.append(message)
        finally:
            self.active_sends -= 1

    async def recv(self) -> str | bytes:
        item = await self.incoming.get()
        if isinstance(item, BaseException):
            raise item
        return item

    async def close(self, *, code: int = 1000, reason: str = "") -> None:
        self.close_calls.append((code, reason))
        if self.closed:
            return
        self.closed = True
        self.incoming.put_nowait(WebSocketClosed(code, reason or "client_close"))

    async def push(self, message: str | bytes | BaseException) -> None:
        await self.incoming.put(message)


@dataclass
class ScriptedConnector:
    connection: ScriptedWebSocketConnection

    def __post_init__(self) -> None:
        self.configs: list[WebSocketConnectionConfig] = []

    async def connect(self, config: WebSocketConnectionConfig) -> ScriptedWebSocketConnection:
        self.configs.append(config)
        return self.connection
