from __future__ import annotations

from app.assistant.audio.device_registry import PyAudioDeviceRegistry, public_device_key
from app.assistant.audio.gate6_contracts import (
    AudioRouteState,
    DeviceDirection,
    DevicePreference,
    DevicePreferenceMode,
)

from fakes import FakePyAudioManager


def test_registry_resolves_defaults_and_never_exposes_portaudio_index() -> None:
    registry = PyAudioDeviceRegistry(pyaudio_factory=FakePyAudioManager)

    snapshot = registry.snapshot()
    route = registry.resolve(
        DevicePreference(DeviceDirection.INPUT),
        DevicePreference(DeviceDirection.OUTPUT),
    )

    assert len(snapshot.devices) == 3
    assert route.state is AudioRouteState.READY
    assert route.input_device is not None
    assert route.output_device is not None
    assert route.input_device.public_name == "Default Microphone"
    assert route.output_device.public_name == "Default Speakers"
    assert registry.device_index(route.input_device.opaque_device_id, DeviceDirection.INPUT) == 0
    assert "index" not in repr(route.input_device).casefold()
    assert route.input_device.opaque_device_id not in public_device_key(
        route.input_device.opaque_device_id
    )


def test_pinned_device_and_temporary_default_fallback_are_distinct() -> None:
    devices = FakePyAudioManager().devices
    registry = PyAudioDeviceRegistry(pyaudio_factory=lambda: FakePyAudioManager(devices))
    snapshot = registry.snapshot()
    headset = next(item for item in snapshot.devices if item.public_name == "USB Headset")
    pinned = DevicePreference(
        DeviceDirection.INPUT,
        DevicePreferenceMode.PIN_SPECIFIC_DEVICE,
        headset.opaque_device_id,
    )

    route = registry.resolve(pinned, DevicePreference(DeviceDirection.OUTPUT))
    assert route.input_device == headset
    assert route.temporary_input_fallback is False

    devices.pop()
    fallback = registry.resolve(pinned, DevicePreference(DeviceDirection.OUTPUT))
    assert fallback.state is AudioRouteState.READY
    assert fallback.input_device is not None
    assert fallback.input_device.public_name == "Default Microphone"
    assert fallback.temporary_input_fallback is True
    assert fallback.error_code == "pinned_device_temporarily_unavailable"
