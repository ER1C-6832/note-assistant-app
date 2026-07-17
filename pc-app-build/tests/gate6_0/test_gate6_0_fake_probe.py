from __future__ import annotations

from app.assistant.audio.gate6_probe import (
    FakeKeywordSpotter,
    ProbeStatus,
    detect_backend_capabilities,
    make_fake_device_snapshot,
    run_fake_probe_contract,
)


def test_fake_device_inventory_covers_empty_directional_and_duplex() -> None:
    assert make_fake_device_snapshot("empty").devices == ()
    directional = make_fake_device_snapshot("directional").devices
    many = make_fake_device_snapshot("many").devices

    assert any(item.can_input and not item.can_output for item in directional)
    assert any(item.can_output and not item.can_input for item in directional)
    assert any(item.can_input and item.can_output for item in many)


def test_fake_kws_hit_and_cooldown_are_generation_safe() -> None:
    spotter = FakeKeywordSpotter(cooldown_ms=1000)
    spotter.reset(4)

    first = spotter.accept_text("小智小智", 1_000_000_000)
    duplicate = spotter.accept_text("小智小智", 1_500_000_000)
    later = spotter.accept_text("小智小智", 2_100_000_000)

    assert first is not None and first.generation == 4
    assert duplicate is None
    assert later is not None
    spotter.close()


def test_backend_capability_probe_includes_bypass_and_platform_candidates() -> None:
    capabilities = detect_backend_capabilities()
    names = {item.backend.value for item in capabilities}

    assert "webrtc_apm" in names
    assert "windows_system_aec" in names
    assert "macos_voice_processing" in names
    assert "bypass" in names
    assert any(item.backend.value == "bypass" and item.create_success for item in capabilities)


def test_fake_gate6_0_contract_reaches_terminal_zero() -> None:
    report = run_fake_probe_contract()
    value = report.public_dict()

    assert report.status is ProbeStatus.COMPLETE
    assert value["result"]["terminal_zero"] is True
    assert value["terminal"]["microphone_lease"] == "none"
    assert value["terminal"]["worker_threads"] == []
