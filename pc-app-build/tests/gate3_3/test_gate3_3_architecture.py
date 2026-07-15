from __future__ import annotations

from pathlib import Path

PC_BUILD_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PC_BUILD_ROOT.parent
APP_ROOT = PC_BUILD_ROOT / "apps" / "notes-pyside" / "app"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _current_verifiers_covering(test_path: str) -> tuple[Path, ...]:
    return tuple(
        path
        for path in sorted(REPO_ROOT.glob("VERIFY_GATE*.ps1"))
        if test_path in _read(path).replace("\\", "/")
    )


def test_streaming_vad_uses_shared_audio_pipeline_and_single_event_pump() -> None:
    controller = _read(APP_ROOT / "assistant" / "controller.py")
    reducer = _read(APP_ROOT / "assistant" / "state_machine.py")
    engine = _read(APP_ROOT / "assistant" / "audio" / "engine.py")
    vad = _read(APP_ROOT / "assistant" / "audio" / "vad.py")

    assert "assistant-event-pump" in controller
    assert "StartStreamingConversation" in reducer
    assert "StopStreamingConversation" in reducer
    assert "AssistantAudioEngine" in engine
    assert "next_voice_activity" in engine
    assert "EnergyVoiceActivityDetector" in vad
    assert "subprocess" not in engine.lower()
    assert "localhost" not in engine.lower()


def test_streaming_product_controls_and_aurora_projection_exist() -> None:
    panel = _read(APP_ROOT / "qml" / "components" / "AssistantPanel.qml")
    overlay = _read(APP_ROOT / "qml" / "components" / "AssistantOverlay.qml")
    view_model = _read(APP_ROOT / "ui" / "assistant_view_model.py")

    assert 'objectName: "assistantStreamingConversationButton"' in panel
    assert 'objectName: "assistantStreamingVadStatus"' in panel
    assert "requestStreamingConversationToggle" in panel
    assert "requestStreamingConversationToggle" in overlay
    assert "DragHandler" in overlay
    assert "Qt.RightButton" in overlay
    assert "streamingConversationActive" in view_model
    assert "vadStatusText" in view_model
    assert "StreamingConversationState.USER_SPEAKING" in view_model


def test_streaming_capabilities_are_activated_without_claiming_tts_or_barge_in() -> None:
    state = _read(APP_ROOT / "assistant" / "state.py")
    assert "AssistantCapability.STREAMING_CONVERSATION" in state
    assert 'active,\n            "3.3/4.2"' in state
    assert 'AssistantCapability.VAD, active, "3.3"' in state
    assert "AssistantCapability.TTS_PLAYBACK, not_ready" in state
    assert "AssistantCapability.BARGE_IN, not_ready" in state


def test_gate3_3_delivery_and_current_verifier_exist() -> None:
    expected = (
        PC_BUILD_ROOT / "tools" / "verify_gate3_3_fake_streaming.py",
        PC_BUILD_ROOT / "tools" / "verify_gate3_3_real_streaming.py",
        PC_BUILD_ROOT / "docs" / "report" / "GATE3_3_IMPLEMENTATION_REPORT.md",
    )
    for path in expected:
        assert path.is_file(), path

    covering = _current_verifiers_covering("tests/gate3_3")
    assert covering
    for verifier_path in covering:
        verifier = _read(verifier_path).replace("\\", "/")
        assert "tests/gate3_2" in verifier
        assert "tests/gate3_3" in verifier
        assert "verify_gate3_3_fake_streaming.py" in verifier
        assert "$LASTEXITCODE -ne 0" in verifier
        assert "exit 1" in verifier

    runners = tuple(sorted(REPO_ROOT.glob("RUN_GATE3_3_REAL_*.ps1")))
    assert runners
    assert "verify_gate3_3_real_streaming.py" in _read(runners[-1])
