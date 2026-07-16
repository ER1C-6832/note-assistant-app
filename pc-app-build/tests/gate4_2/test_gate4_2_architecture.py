from __future__ import annotations

import dataclasses
import inspect
from pathlib import Path

from app.assistant.playback import runtime_events
from app.assistant.playback.coordinator import PlaybackCoordinator

ROOT = Path(__file__).resolve().parents[2]
PLAYBACK_ROOT = ROOT / "apps" / "notes-pyside" / "app" / "assistant" / "playback"
NETWORK_FILE = (
    ROOT
    / "apps"
    / "notes-pyside"
    / "app"
    / "assistant"
    / "network"
    / "playback_websocket_transport.py"
)


def test_runtime_playback_events_never_define_payload_fields() -> None:
    for _, value in inspect.getmembers(runtime_events, inspect.isclass):
        if value.__module__ != runtime_events.__name__ or not dataclasses.is_dataclass(value):
            continue
        names = {field.name.lower() for field in dataclasses.fields(value)}
        assert not names & {"payload", "data", "pcm", "opus", "packet_bytes"}


def test_playback_hot_path_has_no_subprocess_or_second_runtime() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in PLAYBACK_ROOT.glob("*.py"))
    assert "subprocess" not in text
    assert "multiprocessing" not in text
    assert "QEventLoop" not in text
    assert "asyncio.new_event_loop" not in text


def test_transport_keeps_raw_binary_outside_runtime_event_queue() -> None:
    source = NETWORK_FILE.read_text(encoding="utf-8")
    assert "offer_payload_nowait" in source
    assert "route_binary(payload)" in source
    assert "payload=" not in source.split("route_binary(payload)", maxsplit=1)[1]


def test_coordinator_is_single_engine_owner() -> None:
    source = inspect.getsource(PlaybackCoordinator)
    assert "self._engine" in source
    assert "asyncio.Queue" not in source


def test_stop_and_mode_switch_cancel_playback_before_adapter_effects() -> None:
    runtime_controller = (PLAYBACK_ROOT / "runtime_controller.py").read_text(encoding="utf-8")
    assert "isinstance(effect, StopStreamingConversation)" in runtime_controller
    assert "isinstance(effect, CloseTransport)" in runtime_controller
    assert "isinstance(effect, SetVoiceInteractionMode)" in runtime_controller
    assert "await self._playback_coordinator.cancel" in runtime_controller
