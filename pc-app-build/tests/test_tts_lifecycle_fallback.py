from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.assistant.events import TextTurnCompleted, VoiceTurnCompleted
from app.assistant.network import websocket_transport as ws
from app.assistant.protocol.events import AssistantText, TtsState


class _Clock:
    def __init__(self) -> None:
        self._value = 0

    def now_ns(self) -> int:
        self._value += 1_000_000
        return self._value


class _ConfigProvider:
    async def load_real(self):  # pragma: no cover - not used by these unit tests
        raise AssertionError("network configuration must not be loaded")


class _Connection:
    async def send(self, _message):  # pragma: no cover - not used
        raise AssertionError("socket send must not be used")

    async def recv(self):  # pragma: no cover - not used
        raise AssertionError("socket recv must not be used")

    async def close(self, *, code=1000, reason=""):  # pragma: no cover - not used
        return None


async def _text_active(turn_token: int = 11):
    events = []

    async def sink(event):
        events.append(event)

    active = ws._ActiveConnection(
        generation=2,
        connection=_Connection(),
        event_sink=sink,
        send_queue=asyncio.Queue(),
        session_id="session-1",
        active_text_turn_token=turn_token,
    )
    active.text_sent_ready.set()
    transport = ws.RealWebSocketTransport(config_provider=_ConfigProvider(), clock=_Clock())
    return transport, active, events


async def _voice_active(turn_token: int = 21):
    events = []

    async def sink(event):
        events.append(event)

    active = ws._ActiveConnection(
        generation=2,
        connection=_Connection(),
        event_sink=sink,
        send_queue=asyncio.Queue(),
        session_id="session-1",
        active_voice_turn_token=turn_token,
        active_capture_generation=7,
    )
    transport = ws.RealWebSocketTransport(config_provider=_ConfigProvider(), clock=_Clock())
    return transport, active, events


@pytest.mark.asyncio
async def test_text_tts_start_survives_old_six_second_fallback(monkeypatch):
    monkeypatch.setattr(ws, "TEXT_TURN_SETTLE_SECONDS", 0.01)
    monkeypatch.setattr(ws, "TTS_LIFECYCLE_TIMEOUT_SECONDS", 0.20)
    transport, active, events = await _text_active()

    await transport._dispatch_protocol_event(
        active, TtsState(state="start", session_id="session-1")
    )
    await transport._dispatch_protocol_event(
        active,
        AssistantText(source_type="llm", text="回复正文", session_id="session-1"),
    )
    await asyncio.sleep(0.04)

    assert active.active_text_turn_token == 11
    assert active.text_tts_lifecycle_started is True
    assert not any(isinstance(event, TextTurnCompleted) for event in events)

    await transport._dispatch_protocol_event(
        active,
        TtsState(
            state="sentence_start",
            text="回复正文",
            session_id="session-1",
        ),
    )
    await asyncio.sleep(0.04)
    assert active.active_text_turn_token == 11

    await transport._dispatch_protocol_event(
        active, TtsState(state="stop", session_id="session-1")
    )
    completed = [event for event in events if isinstance(event, TextTurnCompleted)]
    assert active.active_text_turn_token is None
    assert active.text_tts_lifecycle_started is False
    assert len(completed) == 1
    assert completed[0].reason == "tts_stop"


@pytest.mark.asyncio
async def test_voice_tts_start_keeps_turn_until_terminal_state(monkeypatch):
    monkeypatch.setattr(ws, "TEXT_TURN_SETTLE_SECONDS", 0.01)
    monkeypatch.setattr(ws, "TTS_LIFECYCLE_TIMEOUT_SECONDS", 0.20)
    transport, active, events = await _voice_active()

    await transport._dispatch_protocol_event(
        active, TtsState(state="start", session_id="session-1")
    )
    await transport._dispatch_protocol_event(
        active,
        AssistantText(source_type="llm", text="语音回复", session_id="session-1"),
    )
    await asyncio.sleep(0.04)

    assert active.active_voice_turn_token == 21
    assert active.voice_tts_lifecycle_started is True
    assert not any(isinstance(event, VoiceTurnCompleted) for event in events)

    await transport._dispatch_protocol_event(
        active, TtsState(state="stop", session_id="session-1")
    )
    completed = [event for event in events if isinstance(event, VoiceTurnCompleted)]
    assert active.active_voice_turn_token is None
    assert active.voice_tts_lifecycle_started is False
    assert len(completed) == 1
    assert completed[0].reason == "tts_stop"


@pytest.mark.asyncio
async def test_text_only_response_still_uses_short_settle(monkeypatch):
    monkeypatch.setattr(ws, "TEXT_TURN_SETTLE_SECONDS", 0.01)
    transport, active, events = await _text_active(turn_token=31)

    await transport._dispatch_protocol_event(
        active,
        AssistantText(source_type="text", text="纯文本回复", session_id="session-1"),
    )
    await asyncio.sleep(0.04)

    completed = [event for event in events if isinstance(event, TextTurnCompleted)]
    assert active.active_text_turn_token is None
    assert len(completed) == 1
    assert completed[0].reason == "assistant_text_settled"
