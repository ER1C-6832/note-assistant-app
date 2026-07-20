"""Gate 6.2 offline KWS lifecycle and microphone-owner handoff."""

from __future__ import annotations

import asyncio
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Protocol

from ..state import (
    AssistantAudioStatus,
    AssistantEntrySource,
    AssistantPhase,
    AssistantState,
    VoiceInteractionMode,
)
from .gate6_contracts import (
    AudioRouteState,
    CaptureActivity,
    KeywordSpotResult,
    MicrophoneOwner,
    PlaybackActivity,
    ProcessedPcmFrame,
    ProcessingState,
    PublicAudioFormat,
    TimedPcmFrame,
)
from .kws_model_registry import KwsModelFiles, KwsModelRegistry, KwsModelSnapshot
from .pyaudio_adapter import PyAudioCaptureAdapter
from .session_supervisor import AudioSessionSnapshot, AudioSessionSupervisor
from .sherpa_kws import KwsBackendError, SherpaOnnxKeywordSpotter

if False:  # pragma: no cover - typing-only imports without a runtime cycle
    from ..controller import AssistantController
    from ..preferences import AssistantPreferencesStore


KWS_QUEUE_CAPACITY = 64
KWS_COOLDOWN_MS = 1_500
KWS_DEBOUNCE_MS = 250
KWS_AUDIO_FORMAT = PublicAudioFormat(16_000, 1, 2, 20)

KwsHitSink = Callable[[KeywordSpotResult], None]
KwsSnapshotListener = Callable[["OfflineKwsSnapshot"], None]


class KwsCaptureRuntimePort(Protocol):
    @property
    def active(self) -> bool: ...

    @property
    def worker_alive(self) -> bool: ...

    @property
    def queue_size(self) -> int: ...

    @property
    def overflow_count(self) -> int: ...

    def start(self, generation: int, route_generation: int, hit_sink: KwsHitSink) -> None: ...

    def stop(self) -> None: ...


@dataclass(frozen=True, slots=True)
class OfflineKwsSnapshot:
    enabled: bool = False
    status: str = "disabled"
    generation: int = 0
    wake_phrase: str = "小智"
    model_status: str = "unknown"
    model_summary: str = "尚未检查"
    error_code: str | None = None
    worker_alive: bool = False
    capture_stream_active: bool = False
    queue_size: int = 0
    queue_overflow_count: int = 0
    accepted_hit_count: int = 0
    duplicate_hit_count: int = 0
    resume_count: int = 0
    idle_uploaded_frames: int = 0

    def public_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "status": self.status,
            "generation": self.generation,
            "wake_phrase": self.wake_phrase,
            "model_status": self.model_status,
            "model_summary": self.model_summary,
            "error_code": self.error_code,
            "worker_alive": self.worker_alive,
            "capture_stream_active": self.capture_stream_active,
            "queue_size": self.queue_size,
            "queue_overflow_count": self.queue_overflow_count,
            "accepted_hit_count": self.accepted_hit_count,
            "duplicate_hit_count": self.duplicate_hit_count,
            "resume_count": self.resume_count,
            "idle_uploaded_frames": self.idle_uploaded_frames,
        }


class LocalKwsCaptureRuntime:
    """One bounded callback queue, one worker and one selected KWS adapter."""

    def __init__(
        self,
        model: KwsModelFiles,
        supervisor: AudioSessionSupervisor,
        *,
        queue_capacity: int = KWS_QUEUE_CAPACITY,
        spotter_factory: Callable[[KwsModelFiles], SherpaOnnxKeywordSpotter] = (
            SherpaOnnxKeywordSpotter
        ),
    ) -> None:
        self._model = model
        self._supervisor = supervisor
        self._queue_capacity = max(4, int(queue_capacity))
        self._spotter_factory = spotter_factory
        self._lock = threading.RLock()
        self._capture: PyAudioCaptureAdapter | None = None
        self._spotter: SherpaOnnxKeywordSpotter | None = None
        self._queue: queue.Queue[object] | None = None
        self._stop_event: threading.Event | None = None
        self._worker: threading.Thread | None = None
        self._generation: int | None = None
        self._route_generation = 0
        self._overflow_count = 0
        self._sentinel = object()

    @property
    def active(self) -> bool:
        with self._lock:
            return bool(self._capture and self._capture.is_active)

    @property
    def worker_alive(self) -> bool:
        with self._lock:
            worker = self._worker
        return bool(worker and worker.is_alive())

    @property
    def queue_size(self) -> int:
        with self._lock:
            frames = self._queue
        return frames.qsize() if frames is not None else 0

    @property
    def overflow_count(self) -> int:
        with self._lock:
            return self._overflow_count

    def start(self, generation: int, route_generation: int, hit_sink: KwsHitSink) -> None:
        if generation < 0 or route_generation < 0:
            raise ValueError("KWS generations cannot be negative")
        with self._lock:
            if self._generation is not None:
                raise RuntimeError("KWS runtime is already active")
        route = self._supervisor.current_route()
        if (
            route.state is not AudioRouteState.READY
            or route.input_device is None
            or route.route_generation != route_generation
        ):
            raise KwsBackendError("kws_route_unavailable", "KWS input route is unavailable")
        device_index = self._supervisor.registry.device_index(
            route.input_device.opaque_device_id,
            route.input_preference.direction,
        )
        spotter = self._spotter_factory(self._model)
        spotter.reset(generation)
        frames: queue.Queue[object] = queue.Queue(maxsize=self._queue_capacity)
        stop_event = threading.Event()
        capture = PyAudioCaptureAdapter(input_device_index=device_index)
        with self._lock:
            self._generation = generation
            self._route_generation = route_generation
            self._spotter = spotter
            self._queue = frames
            self._stop_event = stop_event
            self._capture = capture
            self._overflow_count = 0

        def accept(frame) -> bool:
            with self._lock:
                if self._generation != generation:
                    return False
            try:
                frames.put_nowait(frame)
            except queue.Full:
                try:
                    frames.get_nowait()
                except queue.Empty:
                    pass
                with self._lock:
                    self._overflow_count += 1
                try:
                    frames.put_nowait(frame)
                except queue.Full:
                    return False
            return True

        worker = threading.Thread(
            target=self._worker_main,
            args=(generation, route_generation, frames, stop_event, spotter, hit_sink),
            name=f"assistant-kws-worker-{generation}",
            daemon=True,
        )
        with self._lock:
            self._worker = worker
        worker.start()
        try:
            capture.start(generation, accept)
        except Exception:
            self.stop()
            raise

    def stop(self) -> None:
        with self._lock:
            generation = self._generation
            capture = self._capture
            frames = self._queue
            stop_event = self._stop_event
            worker = self._worker
            spotter = self._spotter
            self._generation = None
            self._capture = None
            self._stop_event = None
        if stop_event is not None:
            stop_event.set()
        if capture is not None and generation is not None:
            try:
                capture.stop(generation)
            except Exception:
                capture.close()
        if frames is not None:
            try:
                frames.put_nowait(self._sentinel)
            except queue.Full:
                try:
                    frames.get_nowait()
                    frames.put_nowait(self._sentinel)
                except (queue.Empty, queue.Full):
                    pass
        if worker is not None and worker is not threading.current_thread():
            worker.join(timeout=2.0)
        worker_still_alive = bool(worker and worker.is_alive())
        if spotter is not None and not worker_still_alive:
            spotter.close()
        if frames is not None and not worker_still_alive:
            while True:
                try:
                    frames.get_nowait()
                except queue.Empty:
                    break
        with self._lock:
            self._worker = worker if worker_still_alive else None
            self._spotter = spotter if worker_still_alive else None
            self._queue = frames if worker_still_alive else None
            if not worker_still_alive:
                self._route_generation = 0
        if worker_still_alive:
            raise KwsBackendError(
                "kws_worker_stop_timeout",
                "KWS worker did not stop within the bounded timeout",
            )

    def _worker_main(
        self,
        generation: int,
        route_generation: int,
        frames: queue.Queue[object],
        stop_event: threading.Event,
        spotter: SherpaOnnxKeywordSpotter,
        hit_sink: KwsHitSink,
    ) -> None:
        while not stop_event.is_set():
            try:
                value = frames.get(timeout=0.1)
            except queue.Empty:
                continue
            if value is self._sentinel:
                break
            frame = value
            try:
                timed = TimedPcmFrame(
                    route_generation=route_generation,
                    stream_generation=generation,
                    sequence=frame.sequence,
                    monotonic_ns=frame.captured_at_ns,
                    audio_format=KWS_AUDIO_FORMAT,
                    pcm16_le=frame.pcm16_le,
                )
                result = spotter.accept(
                    ProcessedPcmFrame(
                        source=timed,
                        pcm16_le=timed.pcm16_le,
                        processing_state=ProcessingState.BYPASS,
                        backend_public_name="kws_raw_pcm",
                    )
                )
                if result is not None and not stop_event.is_set():
                    hit_sink(result)
            except Exception:
                stop_event.set()
                break


KwsRuntimeFactory = Callable[[KwsModelFiles, AudioSessionSupervisor], KwsCaptureRuntimePort]


class OfflineKwsCoordinator:
    """Apply the frozen pause policy and exactly-once owner handoff/resume rules."""

    def __init__(
        self,
        controller: "AssistantController",
        preferences_store: "AssistantPreferencesStore",
        supervisor: AudioSessionSupervisor,
        model_registry: KwsModelRegistry,
        *,
        runtime_factory: KwsRuntimeFactory = LocalKwsCaptureRuntime,
        cooldown_ms: int = KWS_COOLDOWN_MS,
        debounce_ms: int = KWS_DEBOUNCE_MS,
    ) -> None:
        self._controller = controller
        self._preferences_store = preferences_store
        self._supervisor = supervisor
        self._model_registry = model_registry
        self._runtime_factory = runtime_factory
        self._cooldown_ns = max(0, int(cooldown_ms)) * 1_000_000
        self._debounce_ns = max(0, int(debounce_ms)) * 1_000_000
        self._snapshot = OfflineKwsSnapshot()
        self._listeners: set[KwsSnapshotListener] = set()
        self._runtime: KwsCaptureRuntimePort | None = None
        self._generation = 0
        self._active_route_generation = 0
        self._last_hit_ns: int | None = None
        self._last_pause_ns: int | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._reconcile_task: asyncio.Task[None] | None = None
        self._operation_lock = asyncio.Lock()
        self._unsubscribe_state: Callable[[], None] | None = None
        self._unsubscribe_audio: Callable[[], None] | None = None
        self._started = False
        self._closed = False

    @property
    def snapshot(self) -> OfflineKwsSnapshot:
        runtime = self._runtime
        if runtime is None:
            return self._snapshot
        return replace(
            self._snapshot,
            worker_alive=runtime.worker_alive,
            capture_stream_active=runtime.active,
            queue_size=runtime.queue_size,
            queue_overflow_count=runtime.overflow_count,
        )

    def subscribe(self, listener: KwsSnapshotListener) -> Callable[[], None]:
        self._listeners.add(listener)

        def unsubscribe() -> None:
            self._listeners.discard(listener)

        return unsubscribe

    async def start(self) -> None:
        if self._closed:
            raise RuntimeError("offline KWS coordinator is closed")
        if self._started:
            return
        self._loop = asyncio.get_running_loop()
        self._unsubscribe_state = self._controller.subscribe(self._on_state)
        self._unsubscribe_audio = self._supervisor.subscribe(self._on_audio)
        self._supervisor.microphone_coordinator.bind_wakeword_yield_handler(
            self.yield_to_assistant_capture
        )
        self._started = True
        await self.reconcile()

    async def set_enabled(self, enabled: bool) -> None:
        saved = await asyncio.to_thread(
            self._preferences_store.update_offline_kws_enabled,
            bool(enabled),
        )
        self._snapshot = replace(self._snapshot, enabled=saved.offline_kws_enabled)
        await self.reconcile()

    async def reconcile(self) -> None:
        if self._closed:
            return
        async with self._operation_lock:
            preferences = await asyncio.to_thread(self._preferences_store.load)
            model_snapshot = self._model_registry.snapshot()
            self._snapshot = replace(
                self._snapshot,
                enabled=preferences.offline_kws_enabled,
                wake_phrase=model_snapshot.wake_phrase,
                model_status=model_snapshot.status,
                model_summary=model_snapshot.public_summary,
            )
            desired, pause_reason = self._desired_running(
                self._controller.state,
                self._supervisor.snapshot,
                preferences.offline_kws_enabled,
                model_snapshot,
            )
            route_generation = self._supervisor.snapshot.route_generation
            if self._runtime is not None and (
                not desired or self._active_route_generation != route_generation
            ):
                await self._stop_runtime(release_lease=True, status=pause_reason)
            if desired and self._runtime is None:
                await self._start_runtime(model_snapshot)
            elif not desired and self._runtime is None:
                error_code = model_snapshot.error_code if preferences.offline_kws_enabled else None
                self._snapshot = replace(
                    self._snapshot,
                    status=pause_reason,
                    error_code=error_code,
                    worker_alive=False,
                    capture_stream_active=False,
                    queue_size=0,
                )
                self._notify()

    async def yield_to_assistant_capture(self) -> None:
        """Called by a manual voice start before it acquires the shared lease."""

        if self._closed:
            return
        async with self._operation_lock:
            await self._stop_runtime(release_lease=True, status="paused_for_assistant")

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        task = self._reconcile_task
        self._reconcile_task = None
        if task is not None and task is not asyncio.current_task() and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        async with self._operation_lock:
            await self._stop_runtime(release_lease=True, status="closed")
        self._supervisor.microphone_coordinator.bind_wakeword_yield_handler(None)
        if self._unsubscribe_state is not None:
            self._unsubscribe_state()
            self._unsubscribe_state = None
        if self._unsubscribe_audio is not None:
            self._unsubscribe_audio()
            self._unsubscribe_audio = None
        self._started = False
        self._listeners.clear()

    def diagnostics(self) -> dict[str, object]:
        report = self.snapshot.public_dict()
        task = self._reconcile_task
        report.update(
            {
                "pending_tasks": ([] if task is None or task.done() else [task.get_name()]),
                "microphone_owner": self._supervisor.microphone_coordinator.owner.value,
                "second_python_process": 0,
            }
        )
        return report

    async def _start_runtime(self, model_snapshot: KwsModelSnapshot) -> None:
        route_generation = self._supervisor.snapshot.route_generation
        generation = self._generation + 1
        acquired = await self._supervisor.microphone_coordinator.acquire(
            generation,
            MicrophoneOwner.WAKEWORD_KWS,
            route_generation,
        )
        if not acquired:
            self._snapshot = replace(self._snapshot, status="paused_microphone_busy")
            self._notify()
            return
        runtime: KwsCaptureRuntimePort | None = None
        try:
            runtime = self._runtime_factory(self._model_registry.resolve(), self._supervisor)
            loop = self._loop or asyncio.get_running_loop()

            def hit_sink(result: KeywordSpotResult) -> None:
                loop.call_soon_threadsafe(self._schedule_hit, generation, result)

            await asyncio.to_thread(runtime.start, generation, route_generation, hit_sink)
        except Exception as exc:
            if runtime is not None:
                await asyncio.to_thread(runtime.stop)
            await self._supervisor.microphone_coordinator.release(
                generation,
                MicrophoneOwner.WAKEWORD_KWS,
                route_generation,
            )
            error_code = getattr(exc, "code", "kws_start_failed")
            self._snapshot = replace(
                self._snapshot,
                status="error",
                error_code=str(error_code),
                worker_alive=False,
                capture_stream_active=False,
            )
            self._notify()
            return
        self._runtime = runtime
        self._generation = generation
        self._active_route_generation = route_generation
        self._supervisor.set_capture_activity(CaptureActivity.WAKEWORD_KWS)
        self._snapshot = replace(
            self._snapshot,
            status="listening",
            generation=generation,
            error_code=None,
            worker_alive=True,
            capture_stream_active=True,
            resume_count=self._snapshot.resume_count + 1,
        )
        self._notify()

    async def _stop_runtime(self, *, release_lease: bool, status: str) -> None:
        runtime = self._runtime
        generation = self._generation
        route_generation = self._active_route_generation
        self._runtime = None
        self._active_route_generation = 0
        stop_error: Exception | None = None
        if runtime is not None:
            try:
                await asyncio.to_thread(runtime.stop)
            except Exception as exc:
                stop_error = exc
        if release_lease and generation > 0:
            await self._supervisor.microphone_coordinator.release(
                generation,
                MicrophoneOwner.WAKEWORD_KWS,
                route_generation,
            )
        if self._supervisor.snapshot.capture_activity is CaptureActivity.WAKEWORD_KWS:
            self._supervisor.set_capture_activity(CaptureActivity.INACTIVE)
        self._last_pause_ns = time.perf_counter_ns()
        self._snapshot = replace(
            self._snapshot,
            status="error" if stop_error is not None else status,
            error_code=(
                str(getattr(stop_error, "code", "kws_stop_failed"))
                if stop_error is not None
                else self._snapshot.error_code
            ),
            worker_alive=runtime.worker_alive if runtime is not None else False,
            capture_stream_active=runtime.active if runtime is not None else False,
            queue_size=runtime.queue_size if runtime is not None else 0,
            queue_overflow_count=(runtime.overflow_count if runtime is not None else 0),
        )
        self._notify()

    def _schedule_hit(self, generation: int, result: KeywordSpotResult) -> None:
        if self._closed:
            return
        asyncio.create_task(
            self._handle_hit(generation, result),
            name=f"assistant-kws-hit-{generation}",
        )

    async def _handle_hit(self, generation: int, result: KeywordSpotResult) -> None:
        async with self._operation_lock:
            if self._runtime is None or generation != self._generation:
                return
            now_ns = result.detected_at_ns
            if self._last_hit_ns is not None and now_ns - self._last_hit_ns < self._cooldown_ns:
                self._snapshot = replace(
                    self._snapshot,
                    duplicate_hit_count=self._snapshot.duplicate_hit_count + 1,
                )
                self._notify()
                return
            if self._last_pause_ns is not None and now_ns - self._last_pause_ns < self._debounce_ns:
                self._snapshot = replace(
                    self._snapshot,
                    duplicate_hit_count=self._snapshot.duplicate_hit_count + 1,
                )
                self._notify()
                return
            self._last_hit_ns = now_ns
            next_capture_generation = self._controller.state.audio.capture_generation + 1
            route_generation = self._active_route_generation
            await self._stop_runtime(release_lease=False, status="handoff")
            transferred = await self._supervisor.microphone_coordinator.transfer(
                generation=generation,
                expected_owner=MicrophoneOwner.WAKEWORD_KWS,
                next_owner=MicrophoneOwner.ASSISTANT_CAPTURE,
                next_generation=next_capture_generation,
                route_generation=route_generation,
            )
            if not transferred:
                self._schedule_reconcile()
                return
            self._snapshot = replace(
                self._snapshot,
                accepted_hit_count=self._snapshot.accepted_hit_count + 1,
            )
            self._notify()
        await self._controller.start_streaming_conversation(
            permission_granted=True,
            source=AssistantEntrySource.WAKEWORD,
            wake_keyword=result.keyword_public_name,
        )
        state = self._controller.state
        if not state.conversation.streaming_session_active:
            await self._supervisor.microphone_coordinator.release(
                next_capture_generation,
                MicrophoneOwner.ASSISTANT_CAPTURE,
                route_generation,
            )
        self._schedule_reconcile()

    def _desired_running(
        self,
        state: AssistantState,
        audio: AudioSessionSnapshot,
        enabled: bool,
        model: KwsModelSnapshot,
    ) -> tuple[bool, str]:
        if not enabled:
            return False, "disabled"
        if not model.ready:
            return False, "model_unavailable"
        if not state.enabled or self._controller.closed:
            return False, "paused_disabled"
        if not state.is_connected or state.phase is not AssistantPhase.CONNECTED:
            return False, "paused_runtime_busy"
        if (
            state.conversation.preferred_voice_mode
            is not VoiceInteractionMode.STREAMING_CONVERSATION
        ):
            return False, "paused_voice_mode"
        if (
            state.conversation.streaming_session_active
            or state.conversation.active_voice_turn_token is not None
            or state.conversation.active_text_turn_token is not None
            or state.audio.status is not AssistantAudioStatus.IDLE
        ):
            return False, "paused_runtime_busy"
        if audio.route_state is not AudioRouteState.READY:
            return False, "paused_route"
        if audio.playback_activity is not PlaybackActivity.INACTIVE:
            return False, "paused_playback"
        if audio.capture_activity not in {CaptureActivity.INACTIVE, CaptureActivity.WAKEWORD_KWS}:
            return False, "paused_capture"
        owner = self._supervisor.microphone_coordinator.owner
        if owner not in {MicrophoneOwner.NONE, MicrophoneOwner.WAKEWORD_KWS}:
            return False, "paused_microphone_busy"
        return True, "listening"

    def _on_state(self, _state: AssistantState) -> None:
        self._schedule_reconcile()

    def _on_audio(self, _snapshot: AudioSessionSnapshot) -> None:
        self._schedule_reconcile()

    def _schedule_reconcile(self) -> None:
        if self._closed or not self._started:
            return
        loop = self._loop
        if loop is None or not loop.is_running():
            return
        if threading.current_thread() is threading.main_thread():
            self._ensure_reconcile_task()
        else:
            loop.call_soon_threadsafe(self._ensure_reconcile_task)

    def _ensure_reconcile_task(self) -> None:
        task = self._reconcile_task
        if task is not None and not task.done():
            return
        task = asyncio.create_task(self.reconcile(), name="assistant-kws-reconcile")
        self._reconcile_task = task

        def completed(done: asyncio.Task[None]) -> None:
            if self._reconcile_task is done:
                self._reconcile_task = None

        task.add_done_callback(completed)

    def _notify(self) -> None:
        snapshot = self.snapshot
        for listener in tuple(self._listeners):
            try:
                listener(snapshot)
            except Exception:
                continue
