from __future__ import annotations

from pathlib import Path

import pytest

from app.assistant.audio.engine import MicrophoneLeaseCoordinator
from app.assistant.audio.gate6_contracts import MicrophoneOwner
from app.assistant.audio.kws_model_registry import KwsModelRegistry
from app.assistant.preferences import AssistantPreferencesStore


def test_offline_kws_is_default_off_and_round_trips(tmp_path: Path) -> None:
    store = AssistantPreferencesStore(tmp_path / "preferences.json")
    assert store.load().offline_kws_enabled is False
    assert store.update_offline_kws_enabled(True).offline_kws_enabled is True
    assert store.load().offline_kws_enabled is True


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
