"""Application-scoped Gate 6.1 audio session and route supervisor."""

from __future__ import annotations

import asyncio
import math
import struct
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace

from ..preferences import AssistantPreferences, AssistantPreferencesStore
from ..playback.pyaudio_output import PyAudioOutputPlan, probe_output_plan
from .device_registry import PyAudioDeviceRegistry, public_device_key
from .duplex_session import PyAudioDuplexSession
from .duplex_buffers import BoundedTimedPcmBuffer
from .engine import MicrophoneLeaseCoordinator
from .gate6_contracts import (
    AudioDeviceSnapshot,
    AudioRouteEvent,
    AudioRouteState,
    CaptureActivity,
    DeviceDirection,
    DevicePreference,
    DevicePreferenceMode,
    MicrophoneOwner,
    PlaybackActivity,
    ProcessingState,
    ResolvedAudioRoute,
    RouteEventKind,
)
from .ports import PcmFrameSink
from .pyaudio_adapter import PyAudioCaptureAdapter
from .route_observer import PollingAudioRouteObserver

AudioSessionListener = Callable[["AudioSessionSnapshot"], None]
RouteInterruptionHandler = Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class AudioSessionSnapshot:
    route_generation: int = 0
    route_state: AudioRouteState = AudioRouteState.RESOLVING
    capture_activity: CaptureActivity = CaptureActivity.INACTIVE
    playback_activity: PlaybackActivity = PlaybackActivity.INACTIVE
    processing_state: ProcessingState = ProcessingState.BYPASS
    input_device_public_name: str | None = None
    output_device_public_name: str | None = None
    temporary_input_fallback: bool = False
    temporary_output_fallback: bool = False
    error_code: str | None = None
    stale_callback_count: int = 0

    def public_dict(self) -> dict[str, object]:
        return {
            "route_generation": self.route_generation,
            "route_state": self.route_state.value,
            "capture_activity": self.capture_activity.value,
            "playback_activity": self.playback_activity.value,
            "processing_state": self.processing_state.value,
            "input_device_public_name": self.input_device_public_name,
            "output_device_public_name": self.output_device_public_name,
            "temporary_input_fallback": self.temporary_input_fallback,
            "temporary_output_fallback": self.temporary_output_fallback,
            "error_code": self.error_code,
            "stale_callback_count": self.stale_callback_count,
        }


class SupervisorCaptureAdapter:
    """Gate 3 compatibility adapter resolved through the current supervised route."""

    def __init__(self, supervisor: "AudioSessionSupervisor") -> None:
        self._supervisor = supervisor
        self._lock = threading.RLock()
        self._delegate: PyAudioCaptureAdapter | None = None
        self._generation: int | None = None
        self._route_generation = 0
        self._closed = False

    @property
    def input_device_public_name(self) -> str | None:
        with self._lock:
            delegate = self._delegate
        return (
            delegate.input_device_public_name
            if delegate is not None
            else self._supervisor.snapshot.input_device_public_name
        )

    @property
    def is_active(self) -> bool:
        with self._lock:
            return bool(self._delegate and self._delegate.is_active)

    def start(self, generation: int, frame_sink: PcmFrameSink) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("supervised capture adapter is closed")
            if self._delegate is not None:
                raise RuntimeError("one supervised capture is already active")
        route = self._supervisor.current_route()
        if route.state is not AudioRouteState.READY or route.input_device is None:
            raise RuntimeError(route.error_code or "input route is unavailable")
        device_index = self._supervisor.registry.device_index(
            route.input_device.opaque_device_id,
            DeviceDirection.INPUT,
        )
        delegate = PyAudioCaptureAdapter(input_device_index=device_index)
        route_generation = route.route_generation

        def accept_if_current(frame) -> bool:
            if self._supervisor.snapshot.route_generation != route_generation:
                self._supervisor.record_stale_callback()
                return False
            return frame_sink(frame)

        with self._lock:
            self._delegate = delegate
            self._generation = generation
            self._route_generation = route_generation
        self._supervisor.set_capture_activity(CaptureActivity.ASSISTANT)
        try:
            delegate.start(generation, accept_if_current)
        except Exception:
            with self._lock:
                self._delegate = None
                self._generation = None
            self._supervisor.set_capture_activity(CaptureActivity.INACTIVE)
            raise

    def stop(self, generation: int) -> None:
        with self._lock:
            if self._generation is None:
                return
            if self._generation != generation:
                raise RuntimeError("stale generation cannot stop supervised capture")
            delegate = self._delegate
            self._delegate = None
            self._generation = None
        try:
            if delegate is not None:
                delegate.stop(generation)
        finally:
            self._supervisor.set_capture_activity(CaptureActivity.INACTIVE)

    def close(self) -> None:
        with self._lock:
            generation = self._generation
            delegate = self._delegate
            self._closed = True
        if generation is not None:
            self.stop(generation)
        elif delegate is not None:
            delegate.close()


class AudioSessionSupervisor:
    """Single owner of product device resolution and Gate 6 audio facts."""

    def __init__(
        self,
        preferences_store: AssistantPreferencesStore,
        *,
        registry: PyAudioDeviceRegistry | None = None,
        route_observer: PollingAudioRouteObserver | None = None,
        microphone_coordinator: MicrophoneLeaseCoordinator | None = None,
        duplex_session: PyAudioDuplexSession | None = None,
    ) -> None:
        self._preferences_store = preferences_store
        self._preferences = preferences_store.load()
        self.registry = registry or PyAudioDeviceRegistry()
        self._observer = route_observer or PollingAudioRouteObserver(self.registry)
        self._lock = threading.RLock()
        self._refresh_lock = asyncio.Lock()
        self._snapshot = AudioSessionSnapshot()
        self.microphone_coordinator = microphone_coordinator or MicrophoneLeaseCoordinator(
            lambda: self.snapshot.route_generation
        )
        self._device_snapshot = AudioDeviceSnapshot(0, (), 0)
        self._route: ResolvedAudioRoute | None = None
        self._listeners: set[AudioSessionListener] = set()
        self._route_interruption_handler: RouteInterruptionHandler | None = None
        self._route_tasks: set[asyncio.Task[None]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._started = False
        self._closed = False
        self.capture_adapter = SupervisorCaptureAdapter(self)
        self.render_reference_buffer = BoundedTimedPcmBuffer(64)
        self.duplex_capture_buffer = BoundedTimedPcmBuffer(64)
        self.duplex_session = duplex_session or PyAudioDuplexSession(
            self.registry,
            self.current_route,
        )
        self._last_microphone_test: dict[str, object] = {
            "status": "not_run",
            "peak_abs": 0,
            "rms": 0.0,
            "error_code": None,
        }
        self._microphone_test_thread: threading.Thread | None = None

    @property
    def snapshot(self) -> AudioSessionSnapshot:
        with self._lock:
            return self._snapshot

    @property
    def last_microphone_test(self) -> dict[str, object]:
        with self._lock:
            return dict(self._last_microphone_test)

    @property
    def route_observer_running(self) -> bool:
        return self._observer.running

    @property
    def microphone_test_worker_alive(self) -> bool:
        thread = self._microphone_test_thread
        return bool(thread and thread.is_alive())

    def subscribe(self, listener: AudioSessionListener) -> Callable[[], None]:
        with self._lock:
            self._listeners.add(listener)

        def unsubscribe() -> None:
            with self._lock:
                self._listeners.discard(listener)

        return unsubscribe

    def bind_route_interruption_handler(self, handler: RouteInterruptionHandler) -> None:
        self._route_interruption_handler = handler

    async def start(self) -> None:
        if self._closed:
            raise RuntimeError("audio session supervisor is closed")
        if self._started:
            return
        self._loop = asyncio.get_running_loop()
        await self.refresh()
        await asyncio.to_thread(self._observer.start, self._on_route_event)
        self._started = True

    async def refresh(self) -> AudioSessionSnapshot:
        async with self._refresh_lock:
            preferences = await asyncio.to_thread(self._preferences_store.load)
            input_preference, output_preference = self._device_preferences(preferences)
            route = await asyncio.to_thread(
                self.registry.resolve,
                input_preference,
                output_preference,
            )
            device_snapshot = await asyncio.to_thread(self.registry.snapshot)
            with self._lock:
                previous_route_generation = self._snapshot.route_generation
                capture_was_active = self._snapshot.capture_activity is not CaptureActivity.INACTIVE
                playback_was_active = (
                    self._snapshot.playback_activity is not PlaybackActivity.INACTIVE
                )
                self._preferences = preferences
                self._route = route
                self._device_snapshot = device_snapshot
                self._snapshot = replace(
                    self._snapshot,
                    route_generation=route.route_generation,
                    route_state=route.state,
                    input_device_public_name=(
                        route.input_device.public_name if route.input_device else None
                    ),
                    output_device_public_name=(
                        route.output_device.public_name if route.output_device else None
                    ),
                    temporary_input_fallback=route.temporary_input_fallback,
                    temporary_output_fallback=route.temporary_output_fallback,
                    error_code=route.error_code,
                )
            self._notify()
            if (
                previous_route_generation > 0
                and route.route_generation != previous_route_generation
                and (capture_was_active or playback_was_active)
            ):
                self._schedule_route_interruption()
            return self.snapshot

    async def select_device(
        self,
        direction: DeviceDirection,
        mode: DevicePreferenceMode,
        public_key: str | None = None,
    ) -> AudioSessionSnapshot:
        opaque_id: str | None = None
        if mode is DevicePreferenceMode.PIN_SPECIFIC_DEVICE:
            opaque_id = await asyncio.to_thread(
                self.registry.opaque_id_for_public_key,
                str(public_key or ""),
                direction,
            )
            if opaque_id is None:
                raise ValueError("selected audio device is not in the current snapshot")
        kwargs: dict[str, object]
        if direction is DeviceDirection.INPUT:
            kwargs = {"input_mode": mode, "input_device_id": opaque_id}
        else:
            kwargs = {"output_mode": mode, "output_device_id": opaque_id}
        await asyncio.to_thread(
            self._preferences_store.update_audio_device_preferences,
            **kwargs,
        )
        return await self.refresh()

    def current_route(self) -> ResolvedAudioRoute:
        with self._lock:
            route = self._route
            preferences = self._preferences
        if route is not None:
            return route
        input_preference, output_preference = self._device_preferences(preferences)
        route = self.registry.resolve(input_preference, output_preference)
        with self._lock:
            self._route = route
        return route

    def input_device_items(self) -> list[dict[str, object]]:
        return self._device_items(DeviceDirection.INPUT)

    def output_device_items(self) -> list[dict[str, object]]:
        return self._device_items(DeviceDirection.OUTPUT)

    def output_plan(self) -> PyAudioOutputPlan:
        route = self.current_route()
        if route.state is not AudioRouteState.READY or route.output_device is None:
            raise RuntimeError(route.error_code or "output route is unavailable")
        index = self.registry.device_index(
            route.output_device.opaque_device_id,
            DeviceDirection.OUTPUT,
        )
        return probe_output_plan(
            device_index=index,
            device_public_name=route.output_device.public_name,
        )

    async def microphone_test(self, *, duration_seconds: float = 1.0) -> dict[str, object]:
        route = self.current_route()
        if route.state is not AudioRouteState.READY or route.input_device is None:
            raise RuntimeError(route.error_code or "input route is unavailable")
        generation = time.perf_counter_ns()
        acquired = await self.microphone_coordinator.acquire(
            generation,
            MicrophoneOwner.ASSISTANT_CAPTURE,
            route.route_generation,
        )
        if not acquired:
            raise RuntimeError("microphone is busy")
        with self._lock:
            self._last_microphone_test = {
                "status": "running",
                "peak_abs": 0,
                "rms": 0.0,
                "error_code": None,
            }
        observer_was_running = self.route_observer_running
        self.set_capture_activity(CaptureActivity.ASSISTANT)
        try:
            try:
                if observer_was_running:
                    await asyncio.to_thread(self._observer.stop)
                bounded_duration = max(0.25, min(float(duration_seconds), 3.0))
                result = await self._run_microphone_test_bounded(
                    route,
                    bounded_duration,
                    timeout_seconds=bounded_duration + 6.0,
                )
            except Exception as exc:
                with self._lock:
                    self._last_microphone_test = {
                        "status": "failed",
                        "peak_abs": 0,
                        "rms": 0.0,
                        "error_code": f"microphone_test_failed:{type(exc).__name__}",
                    }
                self._notify()
                raise
        finally:
            await self.microphone_coordinator.release(
                generation,
                MicrophoneOwner.ASSISTANT_CAPTURE,
                route.route_generation,
            )
            self.set_capture_activity(CaptureActivity.INACTIVE)
            if observer_was_running and not self.microphone_test_worker_alive and not self._closed:
                await asyncio.to_thread(self._observer.start, self._on_route_event)
        with self._lock:
            self._last_microphone_test = result
        self._notify()
        return dict(result)

    def set_capture_activity(self, activity: CaptureActivity) -> None:
        with self._lock:
            if self._snapshot.capture_activity is activity:
                return
            self._snapshot = replace(self._snapshot, capture_activity=activity)
        self._notify_threadsafe()

    def set_playback_activity(self, activity: PlaybackActivity) -> None:
        with self._lock:
            if self._snapshot.playback_activity is activity:
                return
            self._snapshot = replace(self._snapshot, playback_activity=activity)
        self._notify_threadsafe()

    def record_stale_callback(self) -> None:
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                stale_callback_count=self._snapshot.stale_callback_count + 1,
            )
        self._notify_threadsafe()

    def diagnostics(self) -> dict[str, object]:
        render_stats = self.render_reference_buffer.stats
        capture_stats = self.duplex_capture_buffer.stats
        pending_route_tasks = sorted(
            task.get_name() for task in self._route_tasks if not task.done()
        )
        return {
            **self.snapshot.public_dict(),
            "microphone_lease": self.microphone_coordinator.public_dict(),
            "route_observer_running": self.route_observer_running,
            "duplex_open_stream_count": self.duplex_session.open_stream_count,
            "pending_route_tasks": pending_route_tasks,
            "render_reference_buffer": {
                "size": render_stats.size,
                "capacity": render_stats.capacity,
                "overflow_count": render_stats.overflow_count,
            },
            "duplex_capture_buffer": {
                "size": capture_stats.size,
                "capacity": capture_stats.capacity,
                "overflow_count": capture_stats.overflow_count,
            },
            "microphone_test": self.last_microphone_test,
            "microphone_test_worker_alive": self.microphone_test_worker_alive,
            "macos_status": "deferred_after_windows_gate6",
        }

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await asyncio.to_thread(self._observer.close)
        route_tasks = tuple(task for task in self._route_tasks if not task.done())
        for task in route_tasks:
            task.cancel()
        if route_tasks:
            await asyncio.gather(*route_tasks, return_exceptions=True)
        self._route_tasks.clear()
        await asyncio.to_thread(self.duplex_session.close)
        self.render_reference_buffer.clear()
        self.duplex_capture_buffer.clear()
        self.capture_adapter.close()
        await self.microphone_coordinator.force_release()
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                capture_activity=CaptureActivity.INACTIVE,
                playback_activity=PlaybackActivity.INACTIVE,
                processing_state=ProcessingState.BYPASS,
            )
            self._listeners.clear()
        self._started = False

    async def _run_microphone_test_bounded(
        self,
        route: ResolvedAudioRoute,
        duration_seconds: float,
        *,
        timeout_seconds: float,
    ) -> dict[str, object]:
        if self.microphone_test_worker_alive:
            raise RuntimeError("a microphone test worker is already running")
        completed = threading.Event()
        outcome: dict[str, object] = {}

        def run() -> None:
            try:
                outcome["result"] = self._microphone_test_sync(route, duration_seconds)
            except BaseException as exc:
                outcome["error"] = exc
            finally:
                completed.set()

        worker = threading.Thread(
            target=run,
            name="assistant-microphone-test",
            daemon=True,
        )
        self._microphone_test_thread = worker
        worker.start()
        deadline = time.monotonic() + timeout_seconds
        while not completed.is_set() and time.monotonic() < deadline:
            await asyncio.sleep(0.02)
        if not completed.is_set():
            raise TimeoutError("microphone test exceeded its native timeout")
        worker.join(timeout=0.1)
        self._microphone_test_thread = None
        error = outcome.get("error")
        if isinstance(error, BaseException):
            raise error
        result = outcome.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("microphone test returned no result")
        return result

    def _on_route_event(self, event: AudioRouteEvent) -> None:
        if event.kind is RouteEventKind.INTERRUPTED:
            with self._lock:
                self._snapshot = replace(
                    self._snapshot,
                    route_state=AudioRouteState.INTERRUPTED,
                    error_code=event.error_code,
                )
            self._notify_threadsafe()
        loop = self._loop
        if loop is not None and loop.is_running() and not self._closed:
            loop.call_soon_threadsafe(self._schedule_refresh)

    def _schedule_refresh(self) -> None:
        if self._closed:
            return
        task = asyncio.create_task(self.refresh(), name="assistant-audio-route-refresh")
        self._route_tasks.add(task)
        task.add_done_callback(self._route_tasks.discard)

    def _schedule_route_interruption(self) -> None:
        handler = self._route_interruption_handler
        if handler is None or self._closed:
            return

        async def interrupt() -> None:
            try:
                await handler()
            except asyncio.CancelledError:
                raise
            except Exception:
                return

        task = asyncio.create_task(
            interrupt(),
            name="assistant-audio-route-interruption",
        )
        self._route_tasks.add(task)
        task.add_done_callback(self._route_tasks.discard)

    def _device_items(self, direction: DeviceDirection) -> list[dict[str, object]]:
        with self._lock:
            devices = self._device_snapshot.devices
            preferences = self._preferences
        mode = (
            preferences.audio_input_preference_mode
            if direction is DeviceDirection.INPUT
            else preferences.audio_output_preference_mode
        )
        selected_id = (
            preferences.audio_input_device_id
            if direction is DeviceDirection.INPUT
            else preferences.audio_output_device_id
        )
        values: list[dict[str, object]] = [
            {
                "label": "系统默认",
                "key": "",
                "mode": DevicePreferenceMode.FOLLOW_SYSTEM_DEFAULT.value,
                "selected": mode is DevicePreferenceMode.FOLLOW_SYSTEM_DEFAULT,
                "isDefault": True,
            }
        ]
        for item in devices:
            supported = item.can_input if direction is DeviceDirection.INPUT else item.can_output
            if not supported or not item.available:
                continue
            is_default = (
                item.default_input if direction is DeviceDirection.INPUT else item.default_output
            )
            values.append(
                {
                    "label": item.public_name + ("（系统默认）" if is_default else ""),
                    "key": public_device_key(item.opaque_device_id),
                    "mode": DevicePreferenceMode.PIN_SPECIFIC_DEVICE.value,
                    "selected": (
                        mode is DevicePreferenceMode.PIN_SPECIFIC_DEVICE
                        and selected_id == item.opaque_device_id
                    ),
                    "isDefault": is_default,
                    "hostApi": item.host_api,
                }
            )
        return values

    @staticmethod
    def _device_preferences(
        preferences: AssistantPreferences,
    ) -> tuple[DevicePreference, DevicePreference]:
        return (
            DevicePreference(
                DeviceDirection.INPUT,
                preferences.audio_input_preference_mode,
                preferences.audio_input_device_id,
            ),
            DevicePreference(
                DeviceDirection.OUTPUT,
                preferences.audio_output_preference_mode,
                preferences.audio_output_device_id,
            ),
        )

    def _microphone_test_sync(
        self,
        route: ResolvedAudioRoute,
        duration_seconds: float,
    ) -> dict[str, object]:
        assert route.input_device is not None
        try:
            import pyaudio
        except ImportError as exc:
            raise RuntimeError("pyaudio is not installed") from exc
        with self.registry.native_operation():
            return self._microphone_test_native(route, duration_seconds, pyaudio)

    def _microphone_test_native(
        self,
        route: ResolvedAudioRoute,
        duration_seconds: float,
        pyaudio,
    ) -> dict[str, object]:
        manager = pyaudio.PyAudio()
        stream = None
        peak = 0
        squared_total = 0.0
        sample_count = 0
        callback_status_error_count = 0
        metrics_lock = threading.Lock()

        def callback(in_data, _frame_count, _time_info, status_flags):
            nonlocal peak
            nonlocal squared_total
            nonlocal sample_count
            nonlocal callback_status_error_count
            raw = bytes(in_data)
            if len(raw) % 2:
                return (None, pyaudio.paContinue)
            samples = struct.unpack("<" + "h" * (len(raw) // 2), raw)
            with metrics_lock:
                if status_flags:
                    callback_status_error_count += 1
                if samples:
                    peak = max(peak, max(abs(value) for value in samples))
                    squared_total += sum(float(value) * value for value in samples)
                    sample_count += len(samples)
            return (None, pyaudio.paContinue)

        try:
            index = self.registry.device_index(
                route.input_device.opaque_device_id,
                DeviceDirection.INPUT,
            )
            frames_per_buffer = 320
            stream = manager.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16_000,
                input=True,
                input_device_index=index,
                frames_per_buffer=frames_per_buffer,
                stream_callback=callback,
                start=False,
            )
            stream.start_stream()
            deadline = time.monotonic() + duration_seconds
            while time.monotonic() < deadline:
                if not stream.is_active():
                    break
                time.sleep(min(0.02, max(0.0, deadline - time.monotonic())))
        finally:
            if stream is not None:
                if stream.is_active():
                    stream.stop_stream()
                stream.close()
            manager.terminate()
        with metrics_lock:
            final_peak = peak
            final_squared_total = squared_total
            final_sample_count = sample_count
            final_status_errors = callback_status_error_count
        if final_sample_count <= 0:
            raise RuntimeError("microphone test captured no frames")
        rms = math.sqrt(final_squared_total / final_sample_count)
        return {
            "status": "complete",
            "peak_abs": final_peak,
            "rms": round(rms, 3),
            "sample_count": final_sample_count,
            "callback_status_error_count": final_status_errors,
            "input_device_public_name": route.input_device.public_name,
            "error_code": None,
        }

    def _notify_threadsafe(self) -> None:
        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(self._notify)

    def _notify(self) -> None:
        with self._lock:
            listeners = tuple(self._listeners)
            snapshot = self._snapshot
        for listener in listeners:
            try:
                listener(snapshot)
            except Exception:
                continue
