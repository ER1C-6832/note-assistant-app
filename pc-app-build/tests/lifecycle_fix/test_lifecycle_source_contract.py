from pathlib import Path


APP = Path(__file__).resolve().parents[2] / "apps" / "notes-pyside" / "app"


def test_bootstrap_owns_lifecycle_supervisor() -> None:
    text = (APP / "bootstrap.py").read_text(encoding="utf-8")
    assert "LIFECYCLE_CLOSURE_V1" in text
    assert "SessionLifecycleSupervisor(controller)" in text
    assert "bind_lifecycle_observer" in text
    assert "assistant-lifecycle-supervisor" in text


def test_confirmation_is_bounded_and_single_flight() -> None:
    text = (APP / "ui" / "mcp_ui_adapter.py").read_text(encoding="utf-8")
    assert "LOCAL_CONFIRMATION_TIMEOUT_SECONDS" in text
    assert "asyncio.wait_for" in text
    assert "_active_confirmation_ids" in text
    assert "confirmationActionStarted" in text


def test_qml_closes_rejected_and_timeout_results() -> None:
    text = (APP / "qml" / "Main.qml").read_text(encoding="utf-8")
    assert "confirmationBusy" in text
    assert '"rejected"' in text
    assert '"timeout"' in text
    assert "enabled: !root.confirmationBusy" in text


def test_watchdog_reconnect_is_user_visible_and_generation_safe() -> None:
    events = (APP / "assistant" / "events.py").read_text(encoding="utf-8")
    controller = (APP / "assistant" / "controller.py").read_text(encoding="utf-8")
    reducer = (APP / "assistant" / "state_machine.py").read_text(encoding="utf-8")
    assert 'reason: str = "manual_reconnect"' in events
    assert "message: str | None = None" in events
    assert "reason=reason" in controller
    assert 'code="lifecycle_watchdog_recovery"' in reducer
    assert "invalidate_playback=True" in reducer
