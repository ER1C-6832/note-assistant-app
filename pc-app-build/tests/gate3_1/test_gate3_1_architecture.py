from __future__ import annotations

import ast
from pathlib import Path

PC_BUILD_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PC_BUILD_ROOT.parent
APP_ROOT = PC_BUILD_ROOT / "apps" / "notes-pyside" / "app"
QML_ROOT = APP_ROOT / "qml"
COMPONENTS = QML_ROOT / "components"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_floating_shell_removes_fixed_assistant_column() -> None:
    main = _read(QML_ROOT / "Main.qml")
    overlay = _read(COMPONENTS / "AssistantOverlay.qml")
    floating = _read(COMPONENTS / "AssistantFloatingPanel.qml")

    assert "AssistantOverlay" in main
    assert "AssistantPanel {" not in main
    assert 'objectName: "notesMainRow"' in main
    assert 'objectName: "pageLoader"' in main
    assert "AssistantPanel" in floating
    assert "StackLayout" in floating
    assert 'objectName: "assistantSettingsButton"' in floating
    assert 'objectName: "assistantSettingsPage"' in floating
    assert "AssistantVoiceModeSettings" in floating
    assert "settingsOpen" in floating
    assert "anchors.fill: parent" in overlay
    assert "MouseArea" not in overlay
    assert "DragHandler" in overlay
    assert "requestLauncherPosition" in overlay


def test_aurora_and_voice_settings_are_state_projections() -> None:
    button = _read(COMPONENTS / "AuroraAssistantButton.qml")
    settings = _read(COMPONENTS / "AssistantVoiceModeSettings.qml")
    view_model = _read(APP_ROOT / "ui" / "assistant_view_model.py")

    for token in (
        "auroraVisualState",
        "auroraColorA",
        "auroraColorB",
        "auroraColorC",
        "auroraScale",
        "auroraSpeed",
        "auroraAlpha",
        "compactStatusLabel",
    ):
        assert token in button
        assert token in view_model
    assert "Canvas" in button
    assert 'objectName: "assistantOuterRing"' in button
    assert "anchors.margins: 5" in button
    assert "requestVoiceInteractionMode" in settings
    assert "requestStreamingBargeInEnabled" in settings
    assert "startStreamingConversation" not in settings
    assert "self._state = state" in view_model
    assert "self._phase" not in view_model


def test_preferences_are_separate_from_runtime_credentials() -> None:
    preferences = APP_ROOT / "assistant" / "preferences.py"
    runtime_config = _read(APP_ROOT / "assistant" / "runtime_config.py")
    app_paths = _read(APP_ROOT / "app_paths.py")
    bootstrap = _read(APP_ROOT / "bootstrap.py")

    ast.parse(_read(preferences), filename=str(preferences))
    assert "assistant_preferences.json" in app_paths
    assert "launcher_x_ratio" not in runtime_config
    assert "voice_interaction_mode" not in runtime_config
    assert "AssistantPreferencesStore" in bootstrap
    assert bootstrap.count("AssistantController(") == 1
    assert "ConversationStateMachine(ReconnectPolicy())" in bootstrap


def test_gate3_1_delivery_and_verifier_exist() -> None:
    expected = (
        REPO_ROOT / "VERIFY_GATE3_1.ps1",
        REPO_ROOT / "RUN_GATE3_1_UI_SMOKE.ps1",
        PC_BUILD_ROOT / "tools" / "verify_gate3_1_ui_shell.py",
        PC_BUILD_ROOT / "docs" / "report" / "GATE3_1_IMPLEMENTATION_REPORT.md",
    )
    for path in expected:
        assert path.is_file(), path
