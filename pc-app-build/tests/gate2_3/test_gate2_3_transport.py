from __future__ import annotations

import asyncio
import json

import pytest

from app.assistant.events import (
    ClientHelloSent,
    ProtocolInvalidMessageReceived,
    ProtocolUnknownMessageReceived,
    ServerHelloReceived,
    TransportClosed,
    TransportFailed,
    TransportOpened,
)
from app.assistant.network import RealWebSocketTransport, WebSocketConnectionConfig
from app.assistant.state import AssistantRuntimeMode
from app.assistant.testing import FakeClock

from .fakes import ScriptedConnector, ScriptedWebSocketConnection, StaticConfigProvider


def _config() -> WebSocketConnectionConfig:
    return WebSocketConnectionConfig(
        websocket_url="wss://api.example.test/xiaozhi/v1/?token=must-not-leak",
        websocket_token="real-secret-token",
        device_id="aa:bb:cc:dd:ee:ff",
        client_id="client-123",
    )


@pytest.mark.asyncio
async def test_real_transport_sends_headers_and_hello_before_connected() -> None:
    connection = ScriptedWebSocketConnection(
        messages=['{"type":"hello","transport":"websocket","session_id":"real-session"}']
    )
    connector = ScriptedConnector(connection)
    clock = FakeClock()
    events = []
    connected = asyncio.Event()

    async def sink(event) -> None:
        events.append(event)
        if isinstance(event, ServerHelloReceived):
            connected.set()

    transport = RealWebSocketTransport(
        config_provider=StaticConfigProvider(_config()),
        connector=connector,
        clock=clock,
    )
    open_task = asyncio.create_task(transport.open(1, AssistantRuntimeMode.REAL, sink))
    await asyncio.wait_for(connected.wait(), timeout=1)

    assert isinstance(events[0], TransportOpened)
    assert isinstance(events[1], ClientHelloSent)
    assert json.loads(connection.sent[0]) == {
        "type": "hello",
        "version": 1,
        "features": {"mcp": True},
        "transport": "websocket",
        "audio_params": {
            "format": "opus",
            "sample_rate": 16_000,
            "channels": 1,
            "frame_duration": 20,
        },
    }
    assert connector.configs[0].headers() == {
        "Authorization": "Bearer real-secret-token",
        "Protocol-Version": "1",
        "Device-Id": "aa:bb:cc:dd:ee:ff",
        "Client-Id": "client-123",
    }
    assert events[0].websocket_url_public == "wss://api.example.test/xiaozhi/v1/"

    await transport.close(1, "test_complete", sink)
    await asyncio.wait_for(open_task, timeout=1)
    assert any(isinstance(event, TransportClosed) for event in events)


@pytest.mark.asyncio
async def test_real_transport_has_one_sender_owner_for_concurrent_enqueues() -> None:
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

    open_task = asyncio.create_task(transport.open(3, AssistantRuntimeMode.REAL, sink))
    await asyncio.wait_for(connected.wait(), timeout=1)
    results = await asyncio.gather(
        transport.send_text(3, 1, "第一条", sink),
        transport.send_text(3, 2, "第二条", sink),
        return_exceptions=True,
    )

    assert connection.max_concurrent_sends == 1
    assert [json.loads(item)["text"] for item in connection.sent[1:]] == ["第一条"]
    assert sum(isinstance(result, RuntimeError) for result in results) == 1

    await transport.close(3, "done", sink)
    await asyncio.wait_for(open_task, timeout=1)


@pytest.mark.asyncio
async def test_invalid_and_unknown_json_do_not_close_the_connection() -> None:
    connection = ScriptedWebSocketConnection(
        messages=[
            '{"type":"hello","transport":"websocket","session_id":"session-2"}',
            "{broken-json",
            '{"type":"future_server_event","value":1}',
        ]
    )
    transport = RealWebSocketTransport(
        config_provider=StaticConfigProvider(_config()),
        connector=ScriptedConnector(connection),
        clock=FakeClock(),
    )
    events = []
    routed = asyncio.Event()

    async def sink(event) -> None:
        events.append(event)
        if (
            sum(
                isinstance(
                    item,
                    (ProtocolInvalidMessageReceived, ProtocolUnknownMessageReceived),
                )
                for item in events
            )
            == 2
        ):
            routed.set()

    open_task = asyncio.create_task(transport.open(4, AssistantRuntimeMode.REAL, sink))
    await asyncio.wait_for(routed.wait(), timeout=1)

    assert any(isinstance(event, ProtocolInvalidMessageReceived) for event in events)
    assert any(isinstance(event, ProtocolUnknownMessageReceived) for event in events)
    assert not any(isinstance(event, TransportFailed) for event in events)

    await transport.close(4, "done", sink)
    await asyncio.wait_for(open_task, timeout=1)


@pytest.mark.asyncio
async def test_empty_session_and_hello_timeout_fail_closed() -> None:
    empty_connection = ScriptedWebSocketConnection(
        messages=['{"type":"hello","transport":"websocket","session_id":""}']
    )
    empty_events = []
    empty_transport = RealWebSocketTransport(
        config_provider=StaticConfigProvider(_config()),
        connector=ScriptedConnector(empty_connection),
        clock=FakeClock(),
    )

    async def empty_sink(event) -> None:
        empty_events.append(event)

    await empty_transport.open(5, AssistantRuntimeMode.REAL, empty_sink)
    assert any(
        isinstance(event, ServerHelloReceived) and not event.session_id for event in empty_events
    )
    assert empty_connection.close_calls[-1][0] == 1002

    timeout_connection = ScriptedWebSocketConnection()
    timeout_events = []
    timeout_transport = RealWebSocketTransport(
        config_provider=StaticConfigProvider(_config()),
        connector=ScriptedConnector(timeout_connection),
        clock=FakeClock(),
        hello_timeout_seconds=0.01,
    )

    async def timeout_sink(event) -> None:
        timeout_events.append(event)

    await timeout_transport.open(6, AssistantRuntimeMode.REAL, timeout_sink)
    assert any(
        isinstance(event, TransportFailed) and "hello 超时" in event.message
        for event in timeout_events
    )
