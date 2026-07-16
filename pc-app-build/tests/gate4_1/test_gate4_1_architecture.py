from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

from app.assistant.playback import (
    PlaybackCancelledSignal,
    PlaybackEndedSignal,
    PlaybackFailedSignal,
    PlaybackStartedSignal,
)
from app.assistant.protocol import DownlinkAudioFormat

ROOT = Path(__file__).resolve().parents[2]
PLAYBACK_ROOT = ROOT / "apps" / "notes-pyside" / "app" / "assistant" / "playback"


def test_gate4_0_protocol_export_is_collection_safe() -> None:
    assert DownlinkAudioFormat.__name__ == "DownlinkAudioFormat"
    protocol_init = (
        ROOT / "apps" / "notes-pyside" / "app" / "assistant" / "protocol" / "__init__.py"
    ).read_text(encoding="utf-8")
    assert '"DownlinkAudioFormat"' in protocol_init


def test_playback_foundation_files_are_versioned() -> None:
    expected = {
        "__init__.py",
        "engine.py",
        "fakes.py",
        "format_planner.py",
        "models.py",
        "opus_decoder.py",
        "ports.py",
        "pyaudio_output.py",
        "queues.py",
    }
    assert expected.issubset({path.name for path in PLAYBACK_ROOT.iterdir()})


def test_playback_signals_never_carry_encoded_or_pcm_payload() -> None:
    for signal_type in (
        PlaybackStartedSignal,
        PlaybackEndedSignal,
        PlaybackCancelledSignal,
        PlaybackFailedSignal,
    ):
        names = {field.name for field in fields(signal_type)}
        assert "payload" not in names
        assert "pcm" not in names
        assert "opus" not in names


def test_playback_core_uses_no_subprocess_or_multiprocessing() -> None:
    forbidden = {"subprocess", "multiprocessing"}
    for path in PLAYBACK_ROOT.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert imported.isdisjoint(forbidden), path.name


def test_pyaudio_device_is_not_opened_by_import_or_fake_tests() -> None:
    scaffold = (PLAYBACK_ROOT / "pyaudio_output.py").read_text(encoding="utf-8")
    assert "import pyaudio" not in scaffold
    assert "not activated before Gate 4.2" in scaffold


def test_tts_playback_capability_remains_fail_closed_until_real_gate4_2() -> None:
    state_text = (ROOT / "apps" / "notes-pyside" / "app" / "assistant" / "state.py").read_text(
        encoding="utf-8"
    )
    assert "AssistantCapability.TTS_PLAYBACK, not_ready" in state_text
