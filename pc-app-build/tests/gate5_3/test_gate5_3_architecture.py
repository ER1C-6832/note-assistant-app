from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "apps" / "notes-pyside" / "app"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_gate53_extends_gate52_and_uses_services_only() -> None:
    source = _read(APP / "assistant" / "mcp" / "gate5_3_executor.py")
    assert "class Gate53ToolExecutor(Gate52ToolExecutor)" in source
    assert "PendingConfirmationService" in source
    assert "NoteCommandService" in source
    assert "NoteQueryService" in source
    assert "TagCatalogService" in source
    assert "SqlAlchemy" not in source
    assert "NoteRepository" not in source
    assert "PySide6" not in source


def test_coordinator_projects_generation_and_session_into_tool_call() -> None:
    source = _read(APP / "assistant" / "mcp" / "coordinator.py")
    assert "connection_generation=context.generation" in source
    assert "session_id=context.session_id" in source
    assert "close_generation(generation, reason)" in source


def test_bootstrap_binds_one_gate53_executor_to_ui_and_registry() -> None:
    source = _read(APP / "bootstrap.py")
    assert "Gate53ToolExecutor" in source
    assert "bind_confirmation_actions(mcp_tool_executor)" in source
    assert "ToolRegistry(executor=mcp_tool_executor)" in source
    assert '"mcp-confirmation-service"' in source


def test_qml_confirmation_contains_only_safe_summary_fields() -> None:
    source = _read(APP / "qml" / "Main.qml")
    assert "mcpConfirmationDialog" in source
    assert "confirmPending" in source
    assert "rejectPending" in source
    assert "affected_note_ids" in source
    assert "affected_tags" in source
    assert "pendingConfirmation.content" not in source
