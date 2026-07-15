from __future__ import annotations

import ast
from pathlib import Path

from app.assistant import (
    AssistantCapability,
    AssistantState,
    CapabilityStatus,
)

PC_BUILD_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PC_BUILD_ROOT.parent
APP_ROOT = PC_BUILD_ROOT / "apps" / "notes-pyside" / "app"
ASSISTANT_ROOT = APP_ROOT / "assistant"
TOOLS_ROOT = PC_BUILD_ROOT / "tools"
REPORT_ROOT = PC_BUILD_ROOT / "docs" / "report"
PROTOCOL_REPORT = PC_BUILD_ROOT / "docs" / "spec" / "gate2" / "GATE2_PROTOCOL_COMPATIBILITY.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalized(path: Path) -> str:
    return _read(path).replace("\\", "/")


def _current_verifiers_covering(test_path: str) -> tuple[Path, ...]:
    return tuple(
        path
        for path in sorted(REPO_ROOT.glob("VERIFY_GATE*.ps1"))
        if test_path in _normalized(path)
    )


def test_gate2_7_delivery_files_exist_and_python_sources_parse() -> None:
    expected = (
        TOOLS_ROOT / "verify_gate2_7_fake_acceptance.py",
        TOOLS_ROOT / "verify_gate2_7_real_acceptance.py",
        REPORT_ROOT / "GATE2_7_FINAL_ACCEPTANCE_REPORT.md",
        PROTOCOL_REPORT,
    )
    for path in expected:
        assert path.is_file(), path

    for path in (
        TOOLS_ROOT / "verify_gate2_7_fake_acceptance.py",
        TOOLS_ROOT / "verify_gate2_7_real_acceptance.py",
    ):
        ast.parse(_read(path), filename=str(path))


def test_gate2_7_preserves_single_process_and_single_state_writer() -> None:
    controller = _read(ASSISTANT_ROOT / "controller.py")
    view_model = _read(APP_ROOT / "ui" / "assistant_view_model.py")
    bootstrap = _read(APP_ROOT / "bootstrap.py")
    combined = "\n".join(
        _read(path).lower()
        for path in APP_ROOT.rglob("*")
        if path.is_file() and path.suffix in {".py", ".qml"}
    )

    assert controller.count("self._state = transition.state") == 1
    assert "ConversationStateMachine(" not in view_model
    assert bootstrap.count("AssistantController(") == 1
    for token in (
        "subprocess",
        "multiprocessing",
        "qprocess",
        "http://127.0.0.1",
        "http://localhost",
        "sidecar_client",
        "sidecar_process",
    ):
        assert token not in combined


def test_gate2_7_freezes_future_capabilities_without_fake_product_success() -> None:
    state = AssistantState.disabled()
    active = (
        AssistantCapability.RUNTIME_CORE,
        AssistantCapability.FAKE_TRANSPORT,
        AssistantCapability.REAL_TRANSPORT,
        AssistantCapability.IDENTITY,
        AssistantCapability.ACTIVATION,
        AssistantCapability.TEXT_CONVERSATION,
        AssistantCapability.MANUAL_RECOVERY,
        AssistantCapability.AUTOMATIC_RECOVERY,
    )
    future = (
        AssistantCapability.PUSH_TO_TALK,
        AssistantCapability.TTS_PLAYBACK,
        AssistantCapability.MCP_NOTES,
        AssistantCapability.STREAMING_CONVERSATION,
        AssistantCapability.VAD,
        AssistantCapability.BARGE_IN,
        AssistantCapability.KWS,
    )

    assert all(state.capability_status(item) is CapabilityStatus.ACTIVE for item in active)
    assert all(state.capability_status(item) is CapabilityStatus.NOT_READY for item in future)

    panel = _read(APP_ROOT / "qml" / "components" / "AssistantPanel.qml")
    assert "startPushToTalk" not in panel
    assert "wakeWord" not in panel
    assert "requestSendText" in panel


def test_current_verifier_covers_gate2_7_fake_gate_and_ui_smoke() -> None:
    covering = _current_verifiers_covering("tests/gate2_7")
    assert covering, "current verifier must retain Gate 2.7 regression coverage"

    for path in covering:
        verifier = _normalized(path)
        for test_path in (
            "tests/gate1_7",
            "tests/gate2_1",
            "tests/gate2_2",
            "tests/gate2_3",
            "tests/gate2_4",
            "tests/gate2_5",
            "tests/gate2_6",
            "tests/gate2_7",
        ):
            assert test_path in verifier, path.name
        assert "verify_gate2_7_fake_acceptance.py" in verifier
        assert "verify_gate" in verifier and "ui" in verifier.lower()
        assert "$LASTEXITCODE -ne 0" in verifier
        assert "exit 1" in verifier
        assert "verify_gate2_7_real_acceptance.py" not in verifier


def test_persisted_real_acceptance_tool_keeps_explicit_result_contract() -> None:
    real_tool = _read(TOOLS_ROOT / "verify_gate2_7_real_acceptance.py")

    assert 'status="real_gate_complete"' in real_tool
    assert 'status="real_gate_blocked"' in real_tool
    assert 'status="failed"' in real_tool
    assert "RealOtaActivationClient" in real_tool
    assert "connection_config.headers()" in real_tool
    assert "force_abnormal_close_for_acceptance" in real_tool
    assert "gate_real_text_verified" in real_tool
    assert "activation_client.calls == 1" in real_tool
    assert "websocket_token" not in real_tool
    assert '"session_id":' not in real_tool
    assert '"device_id":' not in real_tool
    assert '"client_id":' not in real_tool
    assert "subprocess" not in real_tool


def test_protocol_and_final_report_keep_truthful_gate_status_contract() -> None:
    protocol = _read(PROTOCOL_REPORT)
    report = _read(REPORT_ROOT / "GATE2_7_FINAL_ACCEPTANCE_REPORT.md")

    assert "## 12. Gate 2.6 AssistantViewModel / QML 实施状态" in protocol
    assert "## 13. Gate 2.7 总验收状态" in protocol
    assert "Fake Gate complete" in report
    assert "Real Gate blocked" in report
    assert "不得声称 Gate 2 全完成" in report
    assert "RUN_GATE2_7_REAL_ACCEPTANCE.ps1" in report
