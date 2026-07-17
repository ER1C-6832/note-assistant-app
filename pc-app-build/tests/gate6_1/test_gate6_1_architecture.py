from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "apps" / "notes-pyside" / "app"


def test_bootstrap_has_one_audio_supervisor_for_capture_playback_and_lease() -> None:
    bootstrap = (APP / "bootstrap.py").read_text(encoding="utf-8")

    assert bootstrap.count("AudioSessionSupervisor(preferences_store)") == 1
    assert "capture=audio_session_supervisor.capture_adapter" in bootstrap
    assert "output_plan_provider=audio_session_supervisor.output_plan" in bootstrap
    assert "microphone_coordinator=audio_session_supervisor.microphone_coordinator" in bootstrap
    assert '"assistant-audio-supervisor"' in bootstrap


def test_device_settings_and_gate6_1_verifiers_are_persistent_assets() -> None:
    qml = APP / "qml" / "components" / "AssistantAudioDeviceSettings.qml"
    panel = APP / "qml" / "components" / "AssistantFloatingPanel.qml"

    assert qml.is_file()
    assert "requestSelectAudioDevice" in qml.read_text(encoding="utf-8")
    assert "AssistantAudioDeviceSettings" in panel.read_text(encoding="utf-8")
    for relative in (
        "VERIFY_GATE6_1.ps1",
        "tools/verify_gate6_1_fake_session.py",
        "tools/verify_gate6_1_cumulative.py",
        "docs/report/GATE6_1_IMPLEMENTATION_REPORT.md",
    ):
        assert (ROOT / relative).is_file(), relative


def test_gate6_1_does_not_enable_product_aec_kws_or_barge_in() -> None:
    supervisor = (APP / "assistant" / "audio" / "session_supervisor.py").read_text(encoding="utf-8")

    assert "KeywordSpotter" not in supervisor
    assert "aec_audio_processing" not in supervisor
    assert "sherpa_onnx" not in supervisor
    assert "ProcessingState.BYPASS" in supervisor


def test_cumulative_verifier_isolates_windows_pytest_temp_cleanup() -> None:
    verifier = (ROOT / "tools" / "verify_gate6_1_cumulative.py").read_text(encoding="utf-8")

    assert "PYTEST_DEBUG_TEMPROOT" in verifier
    assert "--basetemp=" in verifier
    assert "ignore_cleanup_errors=True" in verifier
