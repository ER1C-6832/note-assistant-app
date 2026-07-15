from __future__ import annotations

import ast
from pathlib import Path

PC_BUILD_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PC_BUILD_ROOT.parent
APP_ROOT = PC_BUILD_ROOT / "apps" / "notes-pyside" / "app"
VIEW_MODEL = APP_ROOT / "ui" / "assistant_view_model.py"
PANEL = APP_ROOT / "qml" / "components" / "AssistantPanel.qml"
MAIN_QML = APP_ROOT / "qml" / "Main.qml"
BOOTSTRAP = APP_ROOT / "bootstrap.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalized(path: Path) -> str:
    return _read(path).replace("\\", "/")


def test_gate2_6_files_exist_parse_and_keep_runtime_single_writer() -> None:
    source = _read(VIEW_MODEL)
    ast.parse(source, filename=str(VIEW_MODEL))

    assert PANEL.is_file()
    assert MAIN_QML.is_file()
    assert "self._state = controller.state" in source
    assert "self._state = state" in source
    assert "ConversationStateMachine(" not in source
    assert "AssistantState(" not in source
    assert "self._phase" not in source
    assert "self._connection" not in source
    assert "requestSendText" in source
    assert "requestSimulateAbnormalClose" in source


def test_bootstrap_composes_one_runtime_inside_the_qasync_process() -> None:
    source = _read(BOOTSTRAP)
    tree = ast.parse(source, filename=str(BOOTSTRAP))

    assert source.count("AssistantController(") == 1
    assert "RuntimeTransportRouter(" in source
    assert "ConversationStateMachine(ReconnectPolicy())" in source
    assert 'context.setContextProperty("assistantViewModel"' in source
    assert 'lifecycle.register_async_closer(\n        "assistant-controller"' in source
    assert "assistant_runtime.view_model.initialize" in source
    assert "timeout_seconds=10.0" in source

    forbidden = ("subprocess", "multiprocessing", "qprocess", "localhost", "sidecar")
    lowered = source.lower()
    for token in forbidden:
        assert token not in lowered

    assistant_controller_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _call_name(node) == "AssistantController"
    ]
    assert len(assistant_controller_calls) == 1


def test_assistant_panel_exposes_gate2_6_product_and_developer_surface_only() -> None:
    panel = _read(PANEL)
    main = _read(MAIN_QML)

    for token in (
        "requestSetEnabled",
        "requestConnect",
        "requestDisconnect",
        "requestRetry",
        "requestSendText",
        "lastAssistantText",
        "errorMessage",
        "developerExpanded",
        "requestRuntimeMode",
        "requestRunActivation",
        "requestResetIdentity",
        "lastClientJsonRedacted",
        "lastServerJsonRedacted",
        "capabilityItems",
        "requestSimulateAbnormalClose",
        "requestSimulateFailure",
    ):
        assert token in panel

    assert "AssistantOverlay" in main
    assert "AssistantPanel {" not in main
    floating = _read(APP_ROOT / "qml" / "components" / "AssistantFloatingPanel.qml")
    assert "AssistantPanel" in floating
    assert "viewModelRef: root.assistantModel" in main
    assert "pushToTalk" not in panel
    assert "startPushToTalk" not in panel
    assert "wakeWord" not in panel
    assert "KWS" not in panel


def test_current_verifier_covers_gate2_6_and_keeps_historical_gates() -> None:
    verifiers = tuple(sorted(REPO_ROOT.glob("VERIFY_GATE*.ps1")))
    assert verifiers
    covering = tuple(path for path in verifiers if "tests/gate2_6" in _normalized(path))
    assert covering

    for path in covering:
        source = _normalized(path)
        for historical in (
            "tests/gate1_7",
            "tests/gate2_1",
            "tests/gate2_2",
            "tests/gate2_3",
            "tests/gate2_4",
            "tests/gate2_5",
        ):
            assert historical in source, path.name
        assert "$LASTEXITCODE -ne 0" in source
        assert "exit 1" in source

    smoke_tool = PC_BUILD_ROOT / "tools" / "verify_gate2_6_ui_smoke.py"
    assert smoke_tool.is_file()
    smoke_source = _read(smoke_tool)
    assert "create_application_context" in smoke_source
    assert "context.lifecycle.shutdown" in smoke_source
    assert (PC_BUILD_ROOT / "docs" / "report" / "GATE2_6_IMPLEMENTATION_REPORT.md").is_file()


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None
