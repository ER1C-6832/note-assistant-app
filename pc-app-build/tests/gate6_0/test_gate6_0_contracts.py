from __future__ import annotations

import pytest

from app.assistant.audio.gate6_contracts import (
    AudioDeviceDescriptor,
    AudioDeviceSnapshot,
    AudioPlatform,
    AudioRouteState,
    CaptureActivity,
    DeviceDirection,
    DevicePreference,
    DevicePreferenceMode,
    MicrophoneOwner,
    PlaybackActivity,
    ProcessingState,
    PublicAudioFormat,
    state_projection,
)


def test_audio_format_and_public_projection_are_deterministic() -> None:
    ten_ms = PublicAudioFormat(16_000, 1, 2, 10)
    twenty_ms = PublicAudioFormat(16_000, 1, 2, 20)

    assert ten_ms.samples_per_frame == 160
    assert ten_ms.bytes_per_frame == 320
    assert twenty_ms.samples_per_frame == 320
    assert state_projection(
        capture=CaptureActivity.BARGE_IN_MONITOR,
        playback=PlaybackActivity.PLAYING,
        processing=ProcessingState.WARMING,
        route=AudioRouteState.READY,
    ) == {
        "capture_activity": "barge_in_monitor",
        "playback_activity": "playing",
        "processing_state": "warming",
        "route_state": "ready",
    }


def test_device_identity_is_private_and_snapshot_rejects_duplicate_ids() -> None:
    audio_format = PublicAudioFormat(16_000, 1)
    device = AudioDeviceDescriptor(
        opaque_device_id="private-endpoint-id",
        public_name="Public Microphone",
        platform=AudioPlatform.WINDOWS,
        host_api="WASAPI",
        can_input=True,
        can_output=False,
        default_input=True,
        supported_formats=(audio_format,),
    )

    assert "private-endpoint-id" not in repr(device)
    with pytest.raises(ValueError, match="duplicate"):
        AudioDeviceSnapshot(1, (device, device), captured_at_ns=1)


def test_device_preference_does_not_confuse_default_and_pinned_modes() -> None:
    default = DevicePreference(DeviceDirection.INPUT)
    pinned = DevicePreference(
        DeviceDirection.OUTPUT,
        DevicePreferenceMode.PIN_SPECIFIC_DEVICE,
        "private-output-id",
    )

    assert default.pinned_device_id is None
    assert pinned.mode is DevicePreferenceMode.PIN_SPECIFIC_DEVICE
    assert "private-output-id" not in repr(pinned)

    with pytest.raises(ValueError, match="requires"):
        DevicePreference(DeviceDirection.INPUT, DevicePreferenceMode.PIN_SPECIFIC_DEVICE)


def test_microphone_owner_surface_is_frozen() -> None:
    assert tuple(item.value for item in MicrophoneOwner) == (
        "none",
        "wakeword_kws",
        "assistant_capture",
        "barge_in_monitor",
    )
