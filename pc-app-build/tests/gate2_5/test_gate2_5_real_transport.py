from __future__ import annotations

import asyncio

import pytest

from app.assistant.events import ServerHelloReceived, TransportClosed
from app.assistant.network import RealWebSocketTransport, WebSocketConnectionConfig
from app.assistant.state import AssistantRuntimeMode
from app.assistant.testing import FakeClock

from tests.gate2_3.fakes import (
    ScriptedConnector,
    ScriptedWebSocketConnection,
    StaticConfigProvider,
)


def _config() -> WebSocketConnectionConfig:
    return WebSocketConnectionConfig(
        websocket_url="wss://api.example.test/xiaozhi/v1/",
        websocket_token="real-secret-token",
        device_id="aa:bb:cc:dd:ee:ff",
        client_id="client-123",
    )


@pytest.mark.asyncio
async def test_acceptance_abnormal_close_routes_real_close_code_into_event_pump_boundary() -> None:
    connection = ScriptedWebSocketConnection(
        messages=['{"type":"hello","transport":"websocket","session_id":"session-1"}']
    )
    transport = RealWebSocketTransport(
        config_provider=StaticConfigProvider(_config()),
        connector=ScriptedConnector(connection),
        clock=FakeClock(),
    )
    events = []
    connected = asyncio.Event()

    async def sink(event) -> None:
        events.append(event)
        if isinstance(event, ServerHelloReceived):
            connected.set()

    open_task = asyncio.create_task(transport.open(9, AssistantRuntimeMode.REAL, sink))
    await asyncio.wait_for(connected.wait(), timeout=1)
    await transport.force_abnormal_close_for_acceptance(
        9,
        code=1012,
        reason="gate2_5_real_recovery",
    )
    await asyncio.wait_for(open_task, timeout=1)

    closed = next(event for event in events if isinstance(event, TransportClosed))
    assert closed.generation == 9
    assert closed.code == 1012
    assert closed.reason == "gate2_5_real_recovery"
    assert closed.expected is False
