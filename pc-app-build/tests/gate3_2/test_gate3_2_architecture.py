from __future__ import annotations

from pathlib import Path

PC_BUILD_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = PC_BUILD_ROOT / "apps" / "notes-pyside" / "app"
REPO_ROOT = PC_BUILD_ROOT.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_real_audio_pipeline_files_and_dependencies_exist() -> None:
    audio_root = APP_ROOT / "assistant" / "audio"
    for name in ("engine.py", "pyaudio_adapter.py", "opus_codec.py", "models.py", "queues.py"):
        assert (audio_root / name).is_file(), name

    pyproject = _read(PC_BUILD_ROOT / "pyproject.toml")
    assert "PyAudio" in pyproject
    assert '"av>=13,<17"' in pyproject
    assert "websockets" in pyproject


def test_ptt_keeps_single_event_pump_and_single_sender() -> None:
    controller = _read(APP_ROOT / "assistant" / "controller.py")
    reducer = _read(APP_ROOT / "assistant" / "state_machine.py")
    transport = _read(APP_ROOT / "assistant" / "network" / "websocket_transport.py")
    audio = _read(APP_ROOT / "assistant" / "audio" / "engine.py")

    assert "assistant-event-pump" in controller
    assert "StartPushToTalk" in reducer
    assert "StopPushToTalk" in reducer
    assert "assistant-ws-sender" in transport
    assert "send_audio" in transport
    assert "assistant-audio-worker" in audio
    assert "localhost" not in audio.lower()
    assert "subprocess" not in audio.lower()


def test_product_ptt_control_is_separate_from_draggable_launcher() -> None:
    panel = _read(APP_ROOT / "qml" / "components" / "AssistantPanel.qml")
    overlay = _read(APP_ROOT / "qml" / "components" / "AssistantOverlay.qml")
    view_model = _read(APP_ROOT / "ui" / "assistant_view_model.py")

    assert 'objectName: "assistantPushToTalkButton"' in panel
    assert "onPressed" in panel and "onReleased" in panel
    assert "requestPushToTalkStart" in panel
    assert "requestPushToTalkStop" in panel
    assert "DragHandler" in overlay
    assert "requestPushToTalkStart" not in overlay
    assert "requestPushToTalkStart" in view_model


def test_gate3_2_persistent_assets_and_current_verifier_exist() -> None:
    installer = REPO_ROOT / "INSTALL_GATE3_2_AUDIO_DEPS.ps1"
    fake_tool = PC_BUILD_ROOT / "tools" / "verify_gate3_2_fake_ptt.py"
    real_tool = PC_BUILD_ROOT / "tools" / "verify_gate3_2_real_ptt.py"
    report = PC_BUILD_ROOT / "docs" / "report" / "GATE3_2_IMPLEMENTATION_REPORT.md"
    for path in (installer, fake_tool, real_tool, report):
        assert path.is_file(), path
    assert 'pip install -e ".[dev]"' in _read(installer)

    covering = tuple(
        path
        for path in sorted(REPO_ROOT.glob("VERIFY_GATE*.ps1"))
        if "tests/gate3_2" in _read(path).replace("\\", "/")
    )
    assert covering
    for verifier in covering:
        source = _read(verifier).replace("\\", "/")
        assert "verify_gate3_2_fake_ptt.py" in source
        assert "$LASTEXITCODE -ne 0" in source
        assert "exit 1" in source

    assert "start_push_to_talk" in _read(real_tool)
    assert 'status="real_gate_complete"' not in _read(real_tool) or "real_gate_complete" in _read(
        real_tool
    )
