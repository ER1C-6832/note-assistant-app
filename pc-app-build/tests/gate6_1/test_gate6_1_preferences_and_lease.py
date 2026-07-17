from __future__ import annotations

import pytest

from app.assistant.audio.engine import MicrophoneLeaseCoordinator
from app.assistant.audio.gate6_contracts import DevicePreferenceMode, MicrophoneOwner
from app.assistant.preferences import AssistantPreferencesStore


def test_device_preferences_round_trip_without_public_device_details(tmp_path) -> None:
    path = tmp_path / "assistant_preferences.json"
    store = AssistantPreferencesStore(path)

    store.update_audio_device_preferences(
        input_mode=DevicePreferenceMode.PIN_SPECIFIC_DEVICE,
        input_device_id="private-input-fingerprint",
        output_mode=DevicePreferenceMode.PIN_SPECIFIC_DEVICE,
        output_device_id="private-output-fingerprint",
    )
    loaded = store.load()

    assert loaded.audio_input_device_id == "private-input-fingerprint"
    assert loaded.audio_output_device_id == "private-output-fingerprint"
    text = path.read_text(encoding="utf-8")
    assert "PortAudio index" not in text

    store.update_audio_device_preferences(
        input_mode=DevicePreferenceMode.FOLLOW_SYSTEM_DEFAULT,
        output_mode=DevicePreferenceMode.FOLLOW_SYSTEM_DEFAULT,
    )
    reset = store.load()
    assert reset.audio_input_device_id is None
    assert reset.audio_output_device_id is None


@pytest.mark.asyncio
async def test_microphone_lease_is_owner_and_route_generation_aware() -> None:
    route_generation = 7
    lease = MicrophoneLeaseCoordinator(lambda: route_generation)

    assert await lease.acquire(11) is True
    assert lease.owner is MicrophoneOwner.ASSISTANT_CAPTURE
    assert lease.route_generation == 7
    assert await lease.acquire(12, MicrophoneOwner.WAKEWORD_KWS, 7) is False
    assert await lease.release(11, MicrophoneOwner.WAKEWORD_KWS, 7) is False
    assert await lease.release(11, MicrophoneOwner.ASSISTANT_CAPTURE, 6) is False
    assert (
        await lease.transfer(
            generation=11,
            expected_owner=MicrophoneOwner.ASSISTANT_CAPTURE,
            next_owner=MicrophoneOwner.BARGE_IN_MONITOR,
            next_generation=12,
            route_generation=8,
        )
        is True
    )
    assert lease.public_dict() == {
        "owner": "barge_in_monitor",
        "lease_generation": 12,
        "route_generation": 8,
    }
    assert await lease.release(12, MicrophoneOwner.BARGE_IN_MONITOR, 8) is True
    assert lease.public_dict()["owner"] == "none"
