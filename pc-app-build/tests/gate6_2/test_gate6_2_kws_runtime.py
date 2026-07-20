from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from app.assistant.audio.device_registry import PyAudioDeviceRegistry
from app.assistant.audio.gate6_contracts import (
    DeviceDirection,
    DevicePreferenceMode,
    MicrophoneOwner,
    PlaybackActivity,
)
from app.assistant.audio.kws_model_registry import KwsModelRegistry
from app.assistant.audio.offline_kws import OfflineKwsCoordinator
from app.assistant.audio.session_supervisor import AudioSessionSupervisor
from app.assistant.preferences import AssistantPreferencesStore
from app.assistant.audio.sherpa_kws import KwsBackendError

from gate6_2_fakes import (
    FakeController,
    FakeDuplexSession,
    FakePyAudioManager,
    FakeRouteObserver,
    FakeRuntimeFactory,
)


def _install_fake_model(root: Path) -> KwsModelRegistry:
    registry = KwsModelRegistry(root / "models" / "kws")
    model = registry.resolve()
    model.root.mkdir(parents=True)
    for path in (model.tokens, model.encoder, model.decoder, model.joiner, model.keywords):
        path.write_bytes(b"fake")
    return registry


async def _wait_until(predicate, timeout: float = 1.0) -> None:
    async def wait_loop() -> None:
        while not predicate():
            await asyncio.sleep(0.005)

    await asyncio.wait_for(wait_loop(), timeout=timeout)


async def _build(tmp_path: Path):
    store = AssistantPreferencesStore(tmp_path / "preferences.json")
    store.update_offline_kws_enabled(True)
    supervisor = AudioSessionSupervisor(
        store,
        registry=PyAudioDeviceRegistry(pyaudio_factory=FakePyAudioManager),
        route_observer=FakeRouteObserver(),
        duplex_session=FakeDuplexSession(),
    )
    await supervisor.start()
    controller = FakeController()
    factory = FakeRuntimeFactory()
    coordinator = OfflineKwsCoordinator(
        controller,
        store,
        supervisor,
        _install_fake_model(tmp_path),
        runtime_factory=factory,
    )
    await coordinator.start()
    return store, supervisor, controller, factory, coordinator


@pytest.mark.asyncio
async def test_one_hit_creates_at_most_one_session_and_hands_off_owner(tmp_path: Path) -> None:
    _store, supervisor, controller, factory, coordinator = await _build(tmp_path)
    try:
        assert len(factory.instances) == 1
        assert supervisor.microphone_coordinator.owner is MicrophoneOwner.WAKEWORD_KWS
        runtime = factory.instances[-1]
        now_ns = time.perf_counter_ns()
        runtime.emit_hit(at_ns=now_ns)
        runtime.emit_hit(at_ns=now_ns + 1)

        await _wait_until(lambda: len(controller.starts) == 1)
        assert runtime.active is False
        assert coordinator.snapshot.accepted_hit_count == 1
        assert supervisor.microphone_coordinator.owner is MicrophoneOwner.ASSISTANT_CAPTURE
        assert coordinator.snapshot.idle_uploaded_frames == 0
    finally:
        await coordinator.close()
        await supervisor.close()


@pytest.mark.asyncio
async def test_session_terminal_resumes_once_and_cooldown_rejects_duplicate(tmp_path: Path) -> None:
    _store, supervisor, controller, factory, coordinator = await _build(tmp_path)
    try:
        first_ns = time.perf_counter_ns()
        factory.instances[-1].emit_hit(at_ns=first_ns)
        await _wait_until(lambda: len(controller.starts) == 1)
        capture_generation = controller.state.audio.capture_generation
        await supervisor.microphone_coordinator.release(
            capture_generation,
            MicrophoneOwner.ASSISTANT_CAPTURE,
            supervisor.snapshot.route_generation,
        )
        controller.finish_session()
        await _wait_until(lambda: len(factory.instances) >= 2 and factory.instances[-1].active)
        assert len(factory.instances) == 2
        assert coordinator.snapshot.resume_count == 2

        factory.instances[-1].emit_hit(at_ns=first_ns + 100_000_000)
        await _wait_until(lambda: coordinator.snapshot.duplicate_hit_count == 1)
        assert len(controller.starts) == 1
        assert factory.instances[-1].active is True
    finally:
        await coordinator.close()
        await supervisor.close()


@pytest.mark.asyncio
async def test_manual_capture_preempts_kws_without_two_microphone_owners(tmp_path: Path) -> None:
    _store, supervisor, _controller, factory, coordinator = await _build(tmp_path)
    try:
        acquired = await supervisor.microphone_coordinator.acquire(
            99,
            MicrophoneOwner.ASSISTANT_CAPTURE,
            supervisor.snapshot.route_generation,
        )
        assert acquired is True
        assert factory.instances[0].active is False
        assert supervisor.microphone_coordinator.owner is MicrophoneOwner.ASSISTANT_CAPTURE
        assert coordinator.snapshot.status == "paused_for_assistant"
    finally:
        await coordinator.close()
        await supervisor.close()


@pytest.mark.asyncio
async def test_disable_is_terminal_and_does_not_resume(tmp_path: Path) -> None:
    store, supervisor, controller, factory, coordinator = await _build(tmp_path)
    try:
        await coordinator.set_enabled(False)
        assert store.load().offline_kws_enabled is False
        assert factory.instances[0].active is False
        assert coordinator.snapshot.status == "disabled"
        controller.notify()
        await asyncio.sleep(0.02)
        assert len(factory.instances) == 1
        assert supervisor.microphone_coordinator.owner is MicrophoneOwner.NONE
    finally:
        await coordinator.close()
        await supervisor.close()


@pytest.mark.asyncio
async def test_missing_model_does_not_take_microphone_or_block_manual_mode(tmp_path: Path) -> None:
    store = AssistantPreferencesStore(tmp_path / "preferences.json")
    store.update_offline_kws_enabled(True)
    supervisor = AudioSessionSupervisor(
        store,
        registry=PyAudioDeviceRegistry(pyaudio_factory=FakePyAudioManager),
        route_observer=FakeRouteObserver(),
        duplex_session=FakeDuplexSession(),
    )
    await supervisor.start()
    controller = FakeController()
    coordinator = OfflineKwsCoordinator(
        controller,
        store,
        supervisor,
        KwsModelRegistry(tmp_path / "missing"),
        runtime_factory=FakeRuntimeFactory(),
    )
    try:
        await coordinator.start()
        assert coordinator.snapshot.error_code == "kws_model_missing"
        assert supervisor.microphone_coordinator.owner is MicrophoneOwner.NONE
        assert (
            await supervisor.microphone_coordinator.acquire(
                7,
                MicrophoneOwner.ASSISTANT_CAPTURE,
                supervisor.snapshot.route_generation,
            )
            is True
        )
    finally:
        await coordinator.close()
        await supervisor.close()


@pytest.mark.asyncio
async def test_playback_pauses_kws_and_resumes_one_generation(tmp_path: Path) -> None:
    _store, supervisor, _controller, factory, coordinator = await _build(tmp_path)
    try:
        supervisor.set_playback_activity(PlaybackActivity.PLAYING)
        await _wait_until(lambda: not factory.instances[0].active)
        assert supervisor.microphone_coordinator.owner is MicrophoneOwner.NONE
        assert coordinator.snapshot.status == "paused_playback"

        supervisor.set_playback_activity(PlaybackActivity.INACTIVE)
        await _wait_until(lambda: len(factory.instances) >= 2 and factory.instances[-1].active)
        assert factory.instances[-1].active is True
        assert len(factory.instances) == 2
        assert coordinator.snapshot.resume_count == 2
    finally:
        await coordinator.close()
        await supervisor.close()


@pytest.mark.asyncio
async def test_route_generation_change_restarts_kws_once(tmp_path: Path) -> None:
    _store, supervisor, _controller, factory, coordinator = await _build(tmp_path)
    try:
        first_route_generation = supervisor.snapshot.route_generation
        usb = next(
            item for item in supervisor.input_device_items() if "USB Headset" in item["label"]
        )
        await supervisor.select_device(
            DeviceDirection.INPUT,
            DevicePreferenceMode.PIN_SPECIFIC_DEVICE,
            str(usb["key"]),
        )
        await _wait_until(lambda: len(factory.instances) >= 2 and factory.instances[-1].active)
        assert supervisor.snapshot.route_generation > first_route_generation
        assert factory.instances[0].active is False
        assert factory.instances[-1].active is True
        assert len(factory.instances) == 2
        assert coordinator.snapshot.resume_count == 2
    finally:
        await coordinator.close()
        await supervisor.close()


@pytest.mark.asyncio
async def test_native_backend_failure_releases_lease_and_keeps_manual_capture(
    tmp_path: Path,
) -> None:
    store = AssistantPreferencesStore(tmp_path / "preferences.json")
    store.update_offline_kws_enabled(True)
    supervisor = AudioSessionSupervisor(
        store,
        registry=PyAudioDeviceRegistry(pyaudio_factory=FakePyAudioManager),
        route_observer=FakeRouteObserver(),
        duplex_session=FakeDuplexSession(),
    )
    await supervisor.start()

    def fail_runtime(_model, _supervisor):
        raise KwsBackendError("kws_native_import_failed", "fake import failure")

    coordinator = OfflineKwsCoordinator(
        FakeController(),
        store,
        supervisor,
        _install_fake_model(tmp_path),
        runtime_factory=fail_runtime,
    )
    try:
        await coordinator.start()
        assert coordinator.snapshot.error_code == "kws_native_import_failed"
        assert supervisor.microphone_coordinator.owner is MicrophoneOwner.NONE
        assert await supervisor.microphone_coordinator.acquire(
            88,
            MicrophoneOwner.ASSISTANT_CAPTURE,
            supervisor.snapshot.route_generation,
        )
    finally:
        await coordinator.close()
        await supervisor.close()


@pytest.mark.asyncio
async def test_shutdown_terminal_matrix_is_truthful_and_zero(tmp_path: Path) -> None:
    _store, supervisor, _controller, _factory, coordinator = await _build(tmp_path)
    await coordinator.close()
    terminal = coordinator.diagnostics()
    assert terminal["worker_alive"] is False
    assert terminal["capture_stream_active"] is False
    assert terminal["queue_size"] == 0
    assert terminal["microphone_owner"] == "none"
    assert terminal["pending_tasks"] == []
    assert terminal["idle_uploaded_frames"] == 0
    assert terminal["second_python_process"] == 0
    await supervisor.close()
