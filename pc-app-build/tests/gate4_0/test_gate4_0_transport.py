from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass

import pytest

from app.assistant.events import (
    BinaryAudioReceived,
    ServerHelloReceived,
    TtsStateReceived,
)
from app.assistant.network import WebSocketClosed, WebSocketConnectionConfig
from app.assistant.network.downlink_probe import (
    MetadataOnlyDownlinkProbe,
    ProbeDecodeResult,
)
from app.assistant.network.probing_websocket_transport import (
    ProbingRealWebSocketTransport,
)
from app.assistant.protocol.events import DownlinkAudioFormat
from app.assistant.state import AssistantRuntimeMode
from app.assistant.testing import FakeClock


class FakeDecoder:
    def decode(self, payload: bytes, audio_format: DownlinkAudioFormat):
        return ProbeDecodeResult(
            sample_rate_hz=audio_format.sample_rate_hz,
            channels=audio_format.channels,
            sample_count=320,
        )

    def close(self) -> None:
        pass


class ScriptedConnection:
    def __init__(self, messages) -> None:
        self.incoming: asyncio.Queue[str | bytes | BaseException] = asyncio.Queue()
        for message in messages:
            self.incoming.put_nowait(message)
        self.sent: list[str | bytes] = []
        self.closed = False

    async def send(self, message: str | bytes) -> None:
        self.sent.append(message)

    async def recv(self) -> str | bytes:
        item = await self.incoming.get()
        if isinstance(item, BaseException):
            raise item
        return item

    async def close(self, *, code: int = 1000, reason: str = "") -> None:
        if self.closed:
            return
        self.closed = True
        self.incoming.put_nowait(WebSocketClosed(code, reason or "client_close"))


@dataclass
class ScriptedConnector:
    connection: ScriptedConnection

    async def connect(self, config: WebSocketConnectionConfig) -> ScriptedConnection:
        return self.connection


class StaticConfigProvider:
    async def load_real(self) -> WebSocketConnectionConfig:
        return WebSocketConnectionConfig(
            websocket_url="wss://api.example.test/xiaozhi/v1/",
            websocket_token="secret-token",
            device_id="aa:bb:cc:dd:ee:ff",
            client_id="client-123",
        )


@pytest.mark.asyncio
async def test_binary_payload_bypasses_runtime_event_queue() -> None:
    connection = ScriptedConnection(
        (
            '{"type":"hello","transport":"websocket","session_id":"session-1",'
            '"audio_params":{"format":"opus","sample_rate":16000,'
            '"channels":1,"frame_duration":20}}',
            '{"type":"tts","state":"start","session_id":"session-1"}',
            b"private-opus-packet",
            '{"type":"tts","state":"stop","session_id":"session-1"}',
        )
    )
    probe = MetadataOnlyDownlinkProbe(decoder=FakeDecoder(), packet_capacity=4)
    transport = ProbingRealWebSocketTransport(
        downlink_probe=probe,
        config_provider=StaticConfigProvider(),
        connector=ScriptedConnector(connection),
        clock=FakeClock(),
    )
    events = []
    terminal = asyncio.Event()

    async def sink(event) -> None:
        events.append(event)
        if isinstance(event, TtsStateReceived) and event.state == "stop":
            terminal.set()

    open_task = asyncio.create_task(transport.open(9, AssistantRuntimeMode.REAL, sink))
    await asyncio.wait_for(terminal.wait(), timeout=1)
    await transport.close(9, "test_complete", sink)
    await asyncio.wait_for(open_task, timeout=1)

    hello = next(item for item in events if isinstance(item, ServerHelloReceived))
    binary = next(item for item in events if isinstance(item, BinaryAudioReceived))
    assert hello.session_id == "session-1"
    assert binary.size_bytes == len(b"private-opus-packet")
    assert not _contains_bytes(asdict(binary))

    snapshot = probe.snapshot()
    assert snapshot.binary_packet_count == 1
    assert snapshot.decoded == ProbeDecodeResult(16_000, 1, 320)
    assert snapshot.task_running is False
    assert snapshot.payload_persisted is False


def _contains_bytes(value: object) -> bool:
    if isinstance(value, bytes):
        return True
    if isinstance(value, dict):
        return any(_contains_bytes(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_bytes(item) for item in value)
    return False
