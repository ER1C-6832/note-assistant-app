from __future__ import annotations

import ast
from pathlib import Path

PC_BUILD_ROOT = Path(__file__).resolve().parents[2]
ASSISTANT_ROOT = PC_BUILD_ROOT / "apps" / "notes-pyside" / "app" / "assistant"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_gate2_4_sources_parse_and_keep_single_state_writer() -> None:
    for path in ASSISTANT_ROOT.rglob("*.py"):
        ast.parse(_read(path), filename=str(path))

    controller = _read(ASSISTANT_ROOT / "controller.py")
    state_machine = _read(ASSISTANT_ROOT / "state_machine.py")
    assert controller.count("self._state = transition.state") == 1
    assert "active_text_turn_token" in state_machine
    assert "merge_assistant_transcript" in state_machine
    assert "RuntimeConfigStore" not in state_machine


def test_fake_and_real_share_builder_router_and_real_gate_files_exist() -> None:
    fake = _read(ASSISTANT_ROOT / "testing" / "scripted_transport.py")
    real = _read(ASSISTANT_ROOT / "network" / "websocket_transport.py")
    builder = "XiaozhiMessageBuilder"
    router = "XiaozhiMessageRouter"

    assert builder in fake and router in fake
    assert builder in real and router in real
    assert "listen_detect" in fake
    assert "listen_detect" in real
    assert "active_text_turn_token" in real
    assert "TEXT_TURN_RESPONSE_TIMEOUT_SECONDS" in real

    verifier = _read(PC_BUILD_ROOT.parent / "VERIFY_GATE2_4.ps1")
    real_runner = _read(PC_BUILD_ROOT.parent / "RUN_GATE2_4_REAL_TEXT.ps1")
    assert "tests/gate2_4" in verifier
    assert "$LASTEXITCODE -ne 0" in verifier
    assert "exit 1" in verifier
    assert "verify_gate2_4_real_text.py" in real_runner
    assert (PC_BUILD_ROOT / "docs" / "report" / "GATE2_4_IMPLEMENTATION_REPORT.md").is_file()
