from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = ROOT.parent
APP = ROOT / "apps" / "notes-pyside" / "app"


def test_gate4_final_assets_are_versioned() -> None:
    required = (
        ROOT / "tools" / "verify_gate4_4_cumulative.py",
        ROOT / "tools" / "verify_gate4_4_real_stop_during_playback.py",
        ROOT / "docs" / "spec" / "gate4" / "GATE4_FINAL_FREEZE.md",
        ROOT / "docs" / "report" / "GATE4_4_IMPLEMENTATION_REPORT.md",
        ROOT / "docs" / "report" / "GATE4_FINAL_ACCEPTANCE_REPORT.md",
        ROOT / "docs" / "adr" / "ADR-008-gate4-playback-and-auto-next-turn.md",
        ROOT / "docs" / "amendments" / "PC_ASSISTANT_RUNTIME_MASTER_PLAN_GATE4_AMENDMENT.md",
    )
    assert all(path.is_file() for path in required)


def test_cumulative_verifier_is_tool_only_and_runtime_stays_single_process() -> None:
    verifier = ROOT / "tools" / "verify_gate4_4_cumulative.py"
    verifier_tree = ast.parse(verifier.read_text(encoding="utf-8"))
    verifier_imports = {
        node.names[0].name for node in ast.walk(verifier_tree) if isinstance(node, ast.Import)
    }
    assert "subprocess" in verifier_imports

    runtime_files = tuple((APP / "assistant" / "playback").glob("*.py")) + tuple(
        (APP / "assistant" / "network").glob("*.py")
    )
    for path in runtime_files:
        text = path.read_text(encoding="utf-8")
        assert "multiprocessing" not in text
        assert "subprocess" not in text
        assert "localhost" not in text


def test_final_documents_freeze_current_scope_without_future_overclaim() -> None:
    freeze = (ROOT / "docs" / "spec" / "gate4" / "GATE4_FINAL_FREEZE.md").read_text(
        encoding="utf-8"
    )
    report = (ROOT / "docs" / "report" / "GATE4_FINAL_ACCEPTANCE_REPORT.md").read_text(
        encoding="utf-8"
    )
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    master = (ROOT / "docs" / "PC_ASSISTANT_RUNTIME_MASTER_PLAN.md").read_text(encoding="utf-8")

    assert "Gate 4 实现完成" in freeze
    assert "actual PlaybackEnded" in freeze
    assert "不实现全双工声学插话" in freeze
    assert "real_gate_complete" in report
    assert "当前已实现范围不包含 MCP、KWS 或全双工声学插话" in readme
    assert "| Gate 4 | 已完成" in master
