from __future__ import annotations

import asyncio
import json

import pytest

from app.assistant.events import (
    AssistantTextReceived,
    ClientTextSent,
    ServerHelloReceived,
    TextTurnCompleted,
    TtsStateReceived,
)
from app.assistant.network import RealWebSocketTransport, WebSocketConnectionConfig
from app.assistant.state import AssistantRuntimeMode
from app.assistant.testing import FakeClock

from .fakes import ScriptedConnector, ScriptedWebSocketConnection, StaticConfigProvider


def _config() -> WebSocketConnectionConfig:
    return WebSocketConnectionConfig(
        websocket_url="wss://example.test/xiaozhi",
        websocket_token="secret-token",
        device_id="aa:bb:cc:dd:ee:ff",
        client_id="client-id",
    )


@pytest.mark.asyncio
async def test_real_text_turn_sends_listen_detect_and_tags_reply_with_turn_token() -> None:
    connection = ScriptedWebSocketConnection(
        messages=['{"type":"hello","transport":"websocket","session_id":"session-1"}']
    )
    transport = RealWebSocketTransport(
        config_provider=StaticConfigProvider(_config()),
        connector=ScriptedConnector(connection),
        clock=FakeClock(),
        hello_timeout_seconds=1.0,
    )
    events = []
    connected = asyncio.Event()
    replied = asyncio.Event()

    async def sink(event) -> None:
        events.append(event)
        if isinstance(event, ServerHelloReceived):
            connected.set()
        if isinstance(event, AssistantTextReceived):
            replied.set()

    open_task = asyncio.create_task(transport.open(7, AssistantRuntimeMode.REAL, sink))
    await asyncio.wait_for(connected.wait(), timeout=1)
    await transport.send_text(7, 3, "真实问题", sink)
    await connection.push('{"session_id":"session-1","type":"text","text":"真实回答"}')
    await asyncio.wait_for(replied.wait(), timeout=1)

    outgoing = json.loads(connection.sent[1])
    assert outgoing == {
        "session_id": "session-1",
        "type": "listen",
        "state": "detect",
        "text": "真实问题",
    }
    sent = next(event for event in events if isinstance(event, ClientTextSent))
    reply = next(event for event in events if isinstance(event, AssistantTextReceived))
    assert sent.turn_token == 3
    assert reply.turn_token == 3
    assert reply.text == "真实回答"

    await transport.close(7, "done", sink)
    await asyncio.wait_for(open_task, timeout=1)


@pytest.mark.asyncio
async def test_terminal_tts_completes_turn_without_entering_audio_playback() -> None:
    connection = ScriptedWebSocketConnection(
        messages=['{"type":"hello","transport":"websocket","session_id":"session-2"}']
    )
    transport = RealWebSocketTransport(
        config_provider=StaticConfigProvider(_config()),
        connector=ScriptedConnector(connection),
        clock=FakeClock(),
        hello_timeout_seconds=1.0,
    )
    events = []
    connected = asyncio.Event()
    completed = asyncio.Event()

    async def sink(event) -> None:
        events.append(event)
        if isinstance(event, ServerHelloReceived):
            connected.set()
        if isinstance(event, TextTurnCompleted):
            completed.set()

    open_task = asyncio.create_task(transport.open(8, AssistantRuntimeMode.REAL, sink))
    await asyncio.wait_for(connected.wait(), timeout=1)
    await transport.send_text(8, 1, "问题", sink)
    await connection.push(
        '{"session_id":"session-2","type":"tts","state":"stop","text":"最终回复"}'
    )
    await asyncio.wait_for(completed.wait(), timeout=1)

    tts = next(event for event in events if isinstance(event, TtsStateReceived))
    done = next(event for event in events if isinstance(event, TextTurnCompleted))
    assert tts.turn_token == 1
    assert done.turn_token == 1
    assert done.had_assistant_text is True

    await transport.close(8, "done", sink)
    await asyncio.wait_for(open_task, timeout=1)


@pytest.mark.asyncio
async def test_real_transport_rejects_second_active_text_turn() -> None:
    connection = ScriptedWebSocketConnection(
        messages=['{"type":"hello","transport":"websocket","session_id":"session-3"}']
    )
    transport = RealWebSocketTransport(
        config_provider=StaticConfigProvider(_config()),
        connector=ScriptedConnector(connection),
        clock=FakeClock(),
        hello_timeout_seconds=1.0,
    )
    connected = asyncio.Event()

    async def sink(event) -> None:
        if isinstance(event, ServerHelloReceived):
            connected.set()

    open_task = asyncio.create_task(transport.open(9, AssistantRuntimeMode.REAL, sink))
    await asyncio.wait_for(connected.wait(), timeout=1)
    await transport.send_text(9, 1, "first", sink)
    with pytest.raises(RuntimeError, match="拒绝并行发送"):
        await transport.send_text(9, 2, "second", sink)

    await transport.close(9, "done", sink)
    await asyncio.wait_for(open_task, timeout=1)
