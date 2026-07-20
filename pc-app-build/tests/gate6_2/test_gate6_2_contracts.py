from __future__ import annotations

from pathlib import Path
import asyncio

import pytest

from app.assistant.audio.engine import MicrophoneLeaseCoordinator
from app.assistant.audio.gate6_contracts import MicrophoneOwner
from app.assistant.audio.kws_model_registry import KwsModelRegistry
from app.assistant.preferences import AssistantPreferencesStore


def test_offline_kws_is_default_off_and_round_trips(tmp_path: Path) -> None:
    store = AssistantPreferencesStore(tmp_path / "preferences.json")
    assert store.load().offline_kws_enabled is False
    assert store.load().assistant_auto_connect_enabled is True
    assert store.update_offline_kws_enabled(True).offline_kws_enabled is True
    assert store.load().offline_kws_enabled is True


@pytest.mark.asyncio
@pytest.mark.parametrize("auto_connect", (True, False))
async def test_assistant_is_enabled_on_start_and_auto_connect_is_configurable(
    tmp_path: Path,
    auto_connect: bool,
) -> None:
    pytest.importorskip("PySide6.QtCore")
    from app.assistant import AssistantController, DeviceIdentity
    from app.assistant.testing import OpenSucceeded, ScriptedFakeTransport
    from app.ui.assistant_view_model import AssistantViewModel

    class IdentityManager:
        async def ensure_identity(self):
            return DeviceIdentity(
                device_id="38:00:00:00:00:62",
                client_id="gate6-2-auto-connect",
                serial_number="gate6-2-auto-connect",
                hmac_key="gate6-2-auto-connect",
                generation=1,
                source="test",
            )

        async def reset_identity(self):
            return await self.ensure_identity()

    store = AssistantPreferencesStore(tmp_path / "preferences.json")
    store.update_assistant_auto_connect_enabled(auto_connect)
    transport = ScriptedFakeTransport(
        open_steps=(OpenSucceeded(session_id="gate6-2-auto-connect"),)
    )
    controller = AssistantController(
        transport=transport,
        clock=transport.clock,
        identity_manager=IdentityManager(),
    )
    view_model = AssistantViewModel(
        controller,
        preferences_store=store,
        initial_preferences=store.load(),
    )
    try:
        await controller.use_fake_runtime()
        view_model.initialize()
        await controller.wait_for_state(lambda state: state.enabled)
        if auto_connect:
            await controller.wait_for_state(lambda state: state.is_connected)
        else:
            await asyncio.sleep(0.02)
            assert controller.state.is_connected is False
        assert controller.state.enabled is True
    finally:
        await view_model.close()
        await controller.shutdown()


def test_primary_panel_has_no_assistant_enable_switch() -> None:
    root = Path(__file__).resolve().parents[2]
    panel = (
        root / "apps" / "notes-pyside" / "app" / "qml" / "components" / "AssistantPanel.qml"
    ).read_text(encoding="utf-8")
    settings = (
        root
        / "apps"
        / "notes-pyside"
        / "app"
        / "qml"
        / "components"
        / "AssistantAudioDeviceSettings.qml"
    ).read_text(encoding="utf-8")
    assert "id: enabledSwitch" not in panel
    assert "assistantAutoConnectSwitch" in settings


def test_model_registry_distinguishes_missing_invalid_and_ready(tmp_path: Path) -> None:
    registry = KwsModelRegistry(tmp_path)
    assert registry.snapshot().status == "missing"
    model = registry.resolve()
    model.root.mkdir(parents=True)
    model.tokens.write_text("fake", encoding="utf-8")
    assert registry.snapshot().status == "invalid"
    for path in (model.encoder, model.decoder, model.joiner, model.keywords):
        path.write_bytes(b"fake")
    assert registry.snapshot().status == "ready"
    assert registry.snapshot().wake_phrase == "小智"


@pytest.mark.asyncio
async def test_transferred_assistant_lease_is_idempotently_claimable() -> None:
    lease = MicrophoneLeaseCoordinator(lambda: 4)
    assert await lease.acquire(10, MicrophoneOwner.WAKEWORD_KWS, 4)
    assert await lease.transfer(
        generation=10,
        expected_owner=MicrophoneOwner.WAKEWORD_KWS,
        next_owner=MicrophoneOwner.ASSISTANT_CAPTURE,
        next_generation=11,
        route_generation=4,
    )
    assert await lease.acquire(11, MicrophoneOwner.ASSISTANT_CAPTURE, 4)
    assert not await lease.acquire(12, MicrophoneOwner.ASSISTANT_CAPTURE, 4)


def test_gate6_2_product_and_acceptance_assets_exist() -> None:
    root = Path(__file__).resolve().parents[2]
    app = root / "apps" / "notes-pyside" / "app"
    for path in (
        app / "assistant" / "audio" / "offline_kws.py",
        app / "assistant" / "audio" / "sherpa_kws.py",
        app / "assistant" / "audio" / "kws_model_registry.py",
        root / "VERIFY_GATE6_2.ps1",
        root / "RUN_GATE6_2_REAL_KWS.ps1",
        root / "tools" / "verify_gate6_2_cumulative.py",
        root / "docs" / "report" / "GATE6_2_IMPLEMENTATION_REPORT.md",
    ):
        assert path.is_file(), path
