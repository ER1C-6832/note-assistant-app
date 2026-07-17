from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "apps" / "notes-pyside" / "app"


def test_gate5_1_executor_uses_services_and_typed_ui_bus_only() -> None:
    path = APP / "assistant" / "mcp" / "gate5_1_executor.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    text = path.read_text(encoding="utf-8")

    assert "sqlalchemy" not in imports
    assert "Repository" not in text
    assert "QML" not in text
    assert "UiCommandBus" in text
    assert "NoteQueryService" in text


def test_bootstrap_injects_one_shared_mcp_coordinator_and_ui_adapter() -> None:
    text = (APP / "bootstrap.py").read_text(encoding="utf-8")
    gate52 = (APP / "assistant" / "mcp" / "gate5_2_executor.py").read_text(encoding="utf-8")

    assert "Gate52ToolExecutor" in text
    assert "class Gate52ToolExecutor(Gate51ToolExecutor)" in gate52
    assert "McpScriptedFakeTransport(mcp_coordinator=coordinator)" in text
    assert "mcp_coordinator=coordinator" in text
    assert 'context.setContextProperty("uiCommandAdapter", ui_command_adapter)' in text
    assert '"ui-command-bus"' in text


def test_qml_consumes_navigation_signal_without_object_lookup() -> None:
    main = (APP / "qml" / "Main.qml").read_text(encoding="utf-8")
    adapter = (APP / "ui" / "mcp_ui_adapter.py").read_text(encoding="utf-8")
    assert "onNavigationRequested" in main
    assert "setSearchQueryAndFocus" in main
    assert "findChild" not in adapter
    assert "rootObjects" not in adapter
    assert "PySide6.QtQml" not in adapter
