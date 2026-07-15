from __future__ import annotations

import asyncio

import pytest

from app.assistant import (
    AssistantController,
    AssistantPhase,
    RealWebSocketTransport,
    RuntimeTransportRouter,
    WebSocketConnectionConfig,
)
from app.assistant.network import ScriptedFakeTransport
from app.assistant.testing import FakeClock

from .fakes import ScriptedConnector, ScriptedWebSocketConnection, StaticConfigProvider


def _real_transport(connection, clock, *, token: str = "real-token") -> RealWebSocketTransport:
    return RealWebSocketTransport(
        config_provider=StaticConfigProvider(
            WebSocketConnectionConfig(
                websocket_url="wss://api.example.test/xiaozhi/v1/",
                websocket_token=token,
                device_id="aa:bb:cc:dd:ee:ff",
                client_id="client-id",
            )
        ),
        connector=ScriptedConnector(connection),
        clock=clock,
    )


@pytest.mark.asyncio
async def test_controller_real_mode_reaches_connected_only_after_server_session() -> None:
    clock = FakeClock()
    connection = ScriptedWebSocketConnection(
        messages=['{"type":"hello","transport":"websocket","session_id":"real-session"}']
    )
    real = _real_transport(connection, clock)
    transport = RuntimeTransportRouter(
        fake_transport=ScriptedFakeTransport(clock=clock),
        real_transport=real,
    )
    controller = AssistantController(transport=transport, clock=clock)

    try:
        await controller.enable_assistant()
        await controller.connect()
        connected = await controller.wait_for_state(lambda state: state.is_connected)

        assert connected.phase is AssistantPhase.CONNECTED
        assert connected.connection.session_id == "real-session"
        assert connected.connection.opened_at_ns is not None
        assert connected.connection.hello_sent_at_ns is not None
        assert connected.connection.hello_received_at_ns is not None
        assert connected.diagnostics.gate_real_handshake_verified is True
        assert connected.protocol.last_client_json_redacted is not None
        assert connected.protocol.last_server_json_redacted is not None
        assert "real-token" not in repr(connected)
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_disable_during_real_hello_invalidates_late_result() -> None:
    clock = FakeClock()
    connection = ScriptedWebSocketConnection()
    real = _real_transport(connection, clock)
    controller = AssistantController(
        transport=RuntimeTransportRouter(
            fake_transport=ScriptedFakeTransport(clock=clock),
            real_transport=real,
        ),
        clock=clock,
    )

    try:
        await controller.enable_assistant()
        await controller.connect()
        await controller.wait_for_state(lambda state: state.connection.opened_at_ns is not None)
        old_generation = controller.state.connection.connection_generation

        await controller.disable_assistant()
        assert controller.state.phase is AssistantPhase.DISABLED
        assert controller.state.connection.connection_generation == old_generation + 1

        await connection.push(
            '{"type":"hello","transport":"websocket","session_id":"late-session"}'
        )
        await asyncio.sleep(0)
        assert controller.state.phase is AssistantPhase.DISABLED
        assert controller.state.connection.session_id is None
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_missing_real_token_fails_before_socket_open() -> None:
    clock = FakeClock()
    connection = ScriptedWebSocketConnection()
    real = _real_transport(connection, clock, token="")
    controller = AssistantController(
        transport=RuntimeTransportRouter(
            fake_transport=ScriptedFakeTransport(clock=clock),
            real_transport=real,
        ),
        clock=clock,
    )

    try:
        await controller.enable_assistant()
        await controller.connect()
        failed = await controller.wait_for_state(
            lambda state: state.error is not None and state.error.code == "transport_failure"
        )

        assert failed.phase is AssistantPhase.ERROR
        assert "token" in failed.error.message.lower()
        assert connection.sent == []
    finally:
        await controller.shutdown()
