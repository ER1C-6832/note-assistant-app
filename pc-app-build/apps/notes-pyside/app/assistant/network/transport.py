"""Transport contracts and Fake/Real runtime adapter routing."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

from ..events import AssistantEvent
from ..identity import DeviceIdentityManager
from ..runtime_config import RuntimeConfigStore
from ..state import AssistantRuntimeMode

EventSink = Callable[[AssistantEvent], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class WebSocketConnectionConfig:
    websocket_url: str
    websocket_token: str
    device_id: str
    client_id: str

    def validate(self) -> None:
        if not self.websocket_url.strip():
            raise ValueError("WebSocket URL 未配置")
        if not self.websocket_url.startswith(("ws://", "wss://")):
            raise ValueError("WebSocket URL 必须使用 ws:// 或 wss://")
        if not self.websocket_token.strip():
            raise ValueError("WebSocket token 未配置，请先完成真实 OTA/Activation")
        if not self.device_id.strip():
            raise ValueError("Device ID 未生成")
        if not self.client_id.strip():
            raise ValueError("Client ID 未生成")

    @property
    def public_url(self) -> str:
        return redact_websocket_url(self.websocket_url)

    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.websocket_token}",
            "Protocol-Version": "1",
            "Device-Id": self.device_id,
            "Client-Id": self.client_id,
        }


class ConnectionConfigProvider(Protocol):
    async def load_real(self) -> WebSocketConnectionConfig: ...


class PersistedConnectionConfigProvider:
    """Load the active Real WebSocket credentials from Gate 2.2 storage."""

    def __init__(
        self,
        *,
        config_store: RuntimeConfigStore,
        identity_manager: DeviceIdentityManager,
    ) -> None:
        self._config_store = config_store
        self._identity_manager = identity_manager

    async def load_real(self) -> WebSocketConnectionConfig:
        identity = await self._identity_manager.ensure_identity()
        runtime_config = await asyncio.to_thread(self._config_store.load)
        return WebSocketConnectionConfig(
            websocket_url=runtime_config.real.websocket_url,
            websocket_token=runtime_config.real.websocket_token,
            device_id=identity.device_id,
            client_id=identity.client_id,
        )


class AssistantTransport(Protocol):
    async def open(
        self,
        generation: int,
        runtime_mode: AssistantRuntimeMode,
        event_sink: EventSink,
    ) -> None: ...

    async def send_text(
        self,
        generation: int,
        turn_token: int,
        text: str,
        event_sink: EventSink,
    ) -> None: ...

    async def start_listening(
        self,
        generation: int,
        turn_token: int,
        capture_generation: int,
        mode: str,
        event_sink: EventSink,
    ) -> None: ...

    async def send_audio(
        self,
        generation: int,
        turn_token: int,
        capture_generation: int,
        payload: bytes,
        event_sink: EventSink,
    ) -> None: ...

    async def stop_listening(
        self,
        generation: int,
        turn_token: int,
        capture_generation: int,
        event_sink: EventSink,
    ) -> None: ...

    async def abort(
        self,
        generation: int,
        turn_token: int,
        capture_generation: int,
        reason: str,
        event_sink: EventSink,
    ) -> None: ...

    async def close(
        self,
        generation: int,
        reason: str,
        event_sink: EventSink,
    ) -> None: ...


class RuntimeTransportRouter:
    """Route each connection generation to exactly one Fake or Real adapter."""

    def __init__(
        self,
        *,
        fake_transport: AssistantTransport,
        real_transport: AssistantTransport,
    ) -> None:
        self._fake_transport = fake_transport
        self._real_transport = real_transport
        self._generation_modes: dict[int, AssistantRuntimeMode] = {}
        self._lock = asyncio.Lock()

    async def open(
        self,
        generation: int,
        runtime_mode: AssistantRuntimeMode,
        event_sink: EventSink,
    ) -> None:
        adapter = self._adapter(runtime_mode)
        async with self._lock:
            self._generation_modes[generation] = runtime_mode
        await adapter.open(generation, runtime_mode, event_sink)

    async def send_text(
        self,
        generation: int,
        turn_token: int,
        text: str,
        event_sink: EventSink,
    ) -> None:
        mode = await self._mode_for_generation(generation)
        if mode is None:
            raise RuntimeError("没有与当前 generation 关联的 Transport")
        await self._adapter(mode).send_text(generation, turn_token, text, event_sink)

    async def start_listening(
        self,
        generation: int,
        turn_token: int,
        capture_generation: int,
        mode: str,
        event_sink: EventSink,
    ) -> None:
        adapter = await self._adapter_for_generation(generation)
        await adapter.start_listening(generation, turn_token, capture_generation, mode, event_sink)

    async def send_audio(
        self,
        generation: int,
        turn_token: int,
        capture_generation: int,
        payload: bytes,
        event_sink: EventSink,
    ) -> None:
        adapter = await self._adapter_for_generation(generation)
        await adapter.send_audio(generation, turn_token, capture_generation, payload, event_sink)

    async def stop_listening(
        self,
        generation: int,
        turn_token: int,
        capture_generation: int,
        event_sink: EventSink,
    ) -> None:
        adapter = await self._adapter_for_generation(generation)
        await adapter.stop_listening(generation, turn_token, capture_generation, event_sink)

    async def abort(
        self,
        generation: int,
        turn_token: int,
        capture_generation: int,
        reason: str,
        event_sink: EventSink,
    ) -> None:
        adapter = await self._adapter_for_generation(generation)
        await adapter.abort(generation, turn_token, capture_generation, reason, event_sink)

    async def close(
        self,
        generation: int,
        reason: str,
        event_sink: EventSink,
    ) -> None:
        mode = await self._mode_for_generation(generation)
        if mode is not None:
            try:
                await self._adapter(mode).close(generation, reason, event_sink)
            finally:
                async with self._lock:
                    self._generation_modes.pop(generation, None)
            return

        # A cancelled open effect may remove the generation before the explicit close effect runs.
        # Both adapters must therefore keep close idempotent.
        await self._fake_transport.close(generation, reason, event_sink)
        await self._real_transport.close(generation, reason, event_sink)

    async def _adapter_for_generation(self, generation: int) -> AssistantTransport:
        mode = await self._mode_for_generation(generation)
        if mode is None:
            raise RuntimeError("没有与当前 generation 关联的 Transport")
        return self._adapter(mode)

    async def _mode_for_generation(self, generation: int) -> AssistantRuntimeMode | None:
        async with self._lock:
            return self._generation_modes.get(generation)

    def _adapter(self, mode: AssistantRuntimeMode) -> AssistantTransport:
        return self._fake_transport if mode is AssistantRuntimeMode.FAKE else self._real_transport


def redact_websocket_url(url: str) -> str:
    """Remove credentials, query parameters, and fragments from a public WebSocket URL."""

    try:
        parsed = urlsplit(url.strip())
    except ValueError:
        return "<invalid-websocket-url>"
    if parsed.scheme not in {"ws", "wss"} or not parsed.hostname:
        return "<invalid-websocket-url>"
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    return urlunsplit((parsed.scheme, host, parsed.path, "", ""))
