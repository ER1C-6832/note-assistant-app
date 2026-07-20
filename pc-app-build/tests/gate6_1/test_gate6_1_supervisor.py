from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

import pytest

from app.assistant.audio.device_registry import PyAudioDeviceRegistry
from app.assistant.audio.duplex_buffers import BoundedTimedPcmBuffer
from app.assistant.audio.gate6_contracts import (
    AudioRouteState,
    DeviceDirection,
    DevicePreferenceMode,
    PlaybackActivity,
    PublicAudioFormat,
    TimedPcmFrame,
)
from app.assistant.audio.session_supervisor import AudioSessionSupervisor
from app.assistant.preferences import AssistantPreferencesStore

from fakes import FakeDuplexSession, FakePyAudioManager, FakeRouteObserver


def test_duplex_buffer_is_bounded_and_overflow_is_visible() -> None:
    buffer = BoundedTimedPcmBuffer(2)
    audio_format = PublicAudioFormat(16_000, 1, 2, 10)
    for sequence in range(3):
        buffer.offer(
            TimedPcmFrame(
                route_generation=1,
                stream_generation=1,
                sequence=sequence,
                monotonic_ns=sequence,
                audio_format=audio_format,
                pcm16_le=b"\0" * audio_format.bytes_per_frame,
            )
        )

    assert buffer.stats.size == 2
    assert buffer.stats.overflow_count == 1
    assert buffer.take_nowait().sequence == 1


@pytest.mark.asyncio
async def test_supervisor_owns_route_selection_and_reaches_terminal_zero(tmp_path) -> None:
    registry = PyAudioDeviceRegistry(pyaudio_factory=FakePyAudioManager)
    observer = FakeRouteObserver()
    duplex = FakeDuplexSession()
    supervisor = AudioSessionSupervisor(
        AssistantPreferencesStore(tmp_path / "preferences.json"),
        registry=registry,
        route_observer=observer,
        duplex_session=duplex,
    )
    notifications = []
    supervisor.subscribe(notifications.append)
    route_interruptions: list[str] = []

    async def interrupt_active_audio() -> None:
        route_interruptions.append("interrupted")
        supervisor.set_playback_activity(PlaybackActivity.INACTIVE)

    supervisor.bind_route_interruption_handler(interrupt_active_audio)

    await supervisor.start()
    assert supervisor.snapshot.route_state is AudioRouteState.READY
    assert observer.running is True
    input_items = supervisor.input_device_items()
    headset = next(item for item in input_items if item["label"].startswith("USB Headset"))

    supervisor.set_playback_activity(PlaybackActivity.PLAYING)
    await supervisor.select_device(
        DeviceDirection.INPUT,
        DevicePreferenceMode.PIN_SPECIFIC_DEVICE,
        str(headset["key"]),
    )
    await asyncio.sleep(0)
    assert supervisor.snapshot.input_device_public_name == "USB Headset"
    assert route_interruptions == ["interrupted"]
    assert supervisor.snapshot.playback_activity is PlaybackActivity.INACTIVE
    assert notifications

    await supervisor.close()
    diagnostics = supervisor.diagnostics()
    assert diagnostics["capture_activity"] == "inactive"
    assert diagnostics["playback_activity"] == "inactive"
    assert diagnostics["microphone_lease"]["owner"] == "none"
    assert diagnostics["route_observer_running"] is False
    assert diagnostics["duplex_open_stream_count"] == 0
    assert diagnostics["pending_route_tasks"] == []
    assert diagnostics["microphone_test_worker_alive"] is False
    assert observer.closed is True
    assert duplex.closed is True


@pytest.mark.asyncio
async def test_supervisor_start_and_close_are_idempotent(tmp_path) -> None:
    supervisor = AudioSessionSupervisor(
        AssistantPreferencesStore(tmp_path / "preferences.json"),
        registry=PyAudioDeviceRegistry(pyaudio_factory=FakePyAudioManager),
        route_observer=FakeRouteObserver(),
        duplex_session=FakeDuplexSession(),
    )

    await supervisor.start()
    await supervisor.start()
    await supervisor.close()
    await supervisor.close()

    assert supervisor.diagnostics()["microphone_lease"]["owner"] == "none"
    assert supervisor.diagnostics()["microphone_test_worker_alive"] is False


@pytest.mark.asyncio
async def test_microphone_test_failure_releases_lease_and_activity(tmp_path, monkeypatch) -> None:
    supervisor = AudioSessionSupervisor(
        AssistantPreferencesStore(tmp_path / "preferences.json"),
        registry=PyAudioDeviceRegistry(pyaudio_factory=FakePyAudioManager),
        route_observer=FakeRouteObserver(),
        duplex_session=FakeDuplexSession(),
    )
    await supervisor.start()

    def fail_test(*_args, **_kwargs):
        raise OSError("fake device removed")

    monkeypatch.setattr(supervisor, "_microphone_test_sync", fail_test)
    with pytest.raises(OSError, match="device removed"):
        await supervisor.microphone_test(duration_seconds=0.25)

    diagnostics = supervisor.diagnostics()
    assert diagnostics["capture_activity"] == "inactive"
    assert diagnostics["microphone_lease"]["owner"] == "none"
    assert diagnostics["microphone_test"]["status"] == "failed"
    assert diagnostics["microphone_test"]["error_code"] == "microphone_test_failed:OSError"
    await supervisor.close()


@pytest.mark.asyncio
async def test_microphone_test_uses_bounded_callback_capture(tmp_path, monkeypatch) -> None:
    supervisor = AudioSessionSupervisor(
        AssistantPreferencesStore(tmp_path / "preferences.json"),
        registry=PyAudioDeviceRegistry(pyaudio_factory=FakePyAudioManager),
        route_observer=FakeRouteObserver(),
        duplex_session=FakeDuplexSession(),
    )
    await supervisor.start()

    class FakeStream:
        def __init__(self, callback) -> None:
            self._callback = callback
            self._active = False

        def start_stream(self) -> None:
            self._active = True
            self._callback(b"\x64\x00" * 320, 320, {}, 0)

        def is_active(self) -> bool:
            return self._active

        def stop_stream(self) -> None:
            self._active = False

        def close(self) -> None:
            self._active = False

    class FakeManager:
        def open(self, **kwargs):
            return FakeStream(kwargs["stream_callback"])

        def terminate(self) -> None:
            return None

    monkeypatch.setitem(
        sys.modules,
        "pyaudio",
        SimpleNamespace(paInt16=8, paContinue=0, PyAudio=FakeManager),
    )

    result = await supervisor.microphone_test(duration_seconds=0.25)

    assert result["status"] == "complete"
    assert result["sample_count"] == 320
    assert result["peak_abs"] == 100
    assert result["rms"] == 100.0
    assert result["callback_status_error_count"] == 0
    assert supervisor.diagnostics()["microphone_lease"]["owner"] == "none"
    assert supervisor.route_observer_running is True
    await supervisor.close()
