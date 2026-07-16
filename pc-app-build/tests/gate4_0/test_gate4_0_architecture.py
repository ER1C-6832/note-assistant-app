from __future__ import annotations

import inspect
from pathlib import Path

from app.assistant.events import BinaryAudioReceived
from app.assistant.network import downlink_probe, probing_websocket_transport
from app.assistant.state import AssistantCapability, AssistantState, CapabilityStatus

ROOT = Path(__file__).resolve().parents[2]


def test_probe_hot_path_does_not_import_output_or_process_apis() -> None:
    source = inspect.getsource(downlink_probe)
    transport_source = inspect.getsource(probing_websocket_transport)
    combined = f"{source}\n{transport_source}".lower()

    assert "pyaudio" not in combined
    assert "subprocess" not in combined
    assert "multiprocessing" not in combined
    assert "audiooutput" not in combined


def test_runtime_binary_event_remains_metadata_only() -> None:
    assert tuple(BinaryAudioReceived.__dataclass_fields__) == (
        "at_ns",
        "generation",
        "size_bytes",
    )


def test_probe_source_has_no_audio_dump_extensions() -> None:
    source = inspect.getsource(downlink_probe).lower()
    for suffix in (".opus", ".pcm", ".wav"):
        assert suffix not in source


def test_tts_playback_capability_is_not_activated_by_gate4_0() -> None:
    state = AssistantState.disabled(now_ns=1)
    assert state.capability_status(AssistantCapability.TTS_PLAYBACK) is CapabilityStatus.NOT_READY


def test_gate4_0_real_probe_is_versioned_under_tools() -> None:
    tool = ROOT / "tools" / "verify_gate4_0_real_downlink_probe.py"
    assert tool.is_file()
    source = tool.read_text(encoding="utf-8")
    assert "output_device_opened" in source
    assert "payload_persisted" in source
    assert "ProbingRealWebSocketTransport" in source
