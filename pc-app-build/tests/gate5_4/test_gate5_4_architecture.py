from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "apps" / "notes-pyside" / "app"
TOOLS = ROOT / "tools"


def test_intent_rules_are_deterministic_and_side_effect_free() -> None:
    path = APP / "assistant" / "mcp" / "intent_rules.py"
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom))

    assert not any(name.startswith(("sqlalchemy", "PySide6", "requests")) for name in imports)
    assert "Repository" not in text
    assert "subprocess" not in text
    assert "open(" not in text
    assert "TOOL_INTENT_DESCRIPTIONS" in text


def test_spoken_cleanup_only_enriches_read_query_path() -> None:
    read_executor = (APP / "assistant" / "mcp" / "gate5_1_executor.py").read_text(encoding="utf-8")
    mutation_executor = (APP / "assistant" / "mcp" / "gate5_3_executor.py").read_text(
        encoding="utf-8"
    )

    assert "extract_search_terms" in read_executor
    assert "extract_explicit_note_id" in read_executor
    assert "extract_search_terms" not in mutation_executor
    assert "extract_explicit_note_id" not in mutation_executor


def test_real_manual_runner_does_not_send_scripted_assistant_text() -> None:
    text = (TOOLS / "verify_gate5_4_real_manual.py").read_text(encoding="utf-8")

    assert "natural_language_user_authored" in text
    assert "controller.send_text" not in text
    assert "spoken_command" not in text
    assert "GATE5_4_ACCEPTANCE_CASES" in text


def test_cumulative_runner_keeps_manual_prompts_visible() -> None:
    text = (TOOLS / "verify_gate5_4_cumulative.py").read_text(encoding="utf-8")

    assert "capture_output=not check.interactive" in text
    assert '"gate5_4_real_manual"' in text
    assert "interactive=True" in text


def test_todo_ui_tool_crosses_typed_bus_and_qml_navigation() -> None:
    executor = (APP / "assistant" / "mcp" / "gate5_1_executor.py").read_text(encoding="utf-8")
    bus = (APP / "assistant" / "mcp" / "ui_bus.py").read_text(encoding="utf-8")
    adapter = (APP / "ui" / "mcp_ui_adapter.py").read_text(encoding="utf-8")
    qml = (APP / "qml" / "Main.qml").read_text(encoding="utf-8")

    assert '"ui.show_todos"' in executor
    assert "UiCommandKind.SHOW_TODOS" in executor
    assert 'SHOW_TODOS = "show_todos"' in bus
    assert 'loadCategory("todo")' in adapter
    assert 'command === "show_todos"' in qml
    assert 'root.currentCategory = "todo"' in qml
