"""Gate 6.3+6.4 processed playback monitor and acoustic barge-in coordinator."""

from __future__ import annotations

import asyncio
import importlib.util
import queue
import struct
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Protocol

from ..state import AssistantAudioStatus, AssistantPhase, VoiceActivityState
from ..playback.models import PcmAudioFormat
from ..playback.coordinator import PlaybackCoordinator
from .engine import AssistantAudioEngine
from .gate6_contracts import (
    AudioProcessingMetrics,
    AudioRouteState,
    CaptureActivity,
    MicrophoneOwner,
    PlaybackActivity,
    ProcessingState,
    PublicAudioFormat,
    TimedPcmFrame,
)
from .models import PcmFrame
from .pyaudio_adapter import PyAudioCaptureAdapter
from .session_supervisor import AudioSessionSupervisor
from .vad import EnergyVadConfig, EnergyVoiceActivityDetector
from .webrtc_apm import AudioProcessingUnavailable, WebRtcApmAudioProcessor

if TYPE_CHECKING:
    from ..playback.two_turn_controller import AssistantController


PROCESSING_FORMAT_10_MS = PublicAudioFormat(16_000, 1, 2, 10)
MONITOR_FORMAT_20_MS = PublicAudioFormat(16_000, 1, 2, 20)
MONITOR_QUEUE_CAPACITY = 96
PRE_ROLL_FRAMES = 8

ConfirmSink = Callable[[int, int, tuple[PcmFrame, ...]], None]
FailureSink = Callable[[int, int, str], None]
SnapshotListener = Callable[["AcousticBargeInSnapshot"], None]


@dataclass(frozen=True, slots=True)
class AcousticBargeInSnapshot:
    enabled: bool = False
    available: bool = False
    status: str = "disabled"
    monitor_generation: int = 0
    playback_generation: int = 0
    route_generation: int = 0
    backend_public_name: str = "aec-audio-processing/WebRTC APM"
    processing_state: str = "bypass"
    aec_effective: bool = False
    ns_effective: bool = False
    agc_effective: bool = False
    stream_delay_ms: float | None = None
    monitor_active: bool = False
    worker_alive: bool = False
    capture_queue_size: int = 0
    queue_overflow_count: int = 0
    render_frames: int = 0
    capture_frames: int = 0
    processed_frames: int = 0
    candidate_count: int = 0
    confirmed_count: int = 0
    pre_roll_frames_staged: int = 0
    monitor_uploaded_frames: int = 0
    playback_cancel_count: int = 0
    abort_count: int = 0
    error_code: str | None = None

    def public_dict(self) -> dict[str, object]:
        return {field: getattr(self, field) for field in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class RenderReferenceChunk:
    playback_generation: int
    pcm_format: PcmAudioFormat
    payload: bytes
    rendered_at_ns: int


@dataclass(frozen=True, slots=True)
class _CaptureWork:
    frame: PcmFrame


@dataclass(frozen=True, slots=True)
class _RenderWork:
    chunk: RenderReferenceChunk


class BargeInMonitorRuntimePort(Protocol):
    @property
    def active(self) -> bool: ...

    @property
    def worker_alive(self) -> bool: ...

    @property
    def queue_size(self) -> int: ...

    @property
    def overflow_count(self) -> int: ...

    def start(
        self,
        monitor_generation: int,
        route_generation: int,
        playback_generation: int,
        confirm_sink: ConfirmSink,
        failure_sink: FailureSink,
    ) -> None: ...

    def offer_render(self, chunk: RenderReferenceChunk) -> bool: ...

    def metrics(self) -> AudioProcessingMetrics | None: ...

    def stop(self) -> None: ...


ProcessorFactory = Callable[[int], WebRtcApmAudioProcessor]


class LocalBargeInMonitorRuntime:
    """One capture callback, one bounded work queue and one processed-only VAD worker."""

    def __init__(
        self,
        supervisor: AudioSessionSupervisor,
        *,
        processor_factory: ProcessorFactory | None = None,
        queue_capacity: int = MONITOR_QUEUE_CAPACITY,
    ) -> None:
        self._supervisor = supervisor
        self._processor_factory = processor_factory or (
            lambda delay_ms: WebRtcApmAudioProcessor(
                stream_delay_ms=delay_ms,
                enable_ns=False,
            )
        )
        self._queue_capacity = max(16, int(queue_capacity))
        self._lock = threading.RLock()
        self._capture: PyAudioCaptureAdapter | None = None
        self._processor: WebRtcApmAudioProcessor | None = None
        self._queue: queue.Queue[object] | None = None
        self._stop_event: threading.Event | None = None
        self._worker: threading.Thread | None = None
        self._monitor_generation: int | None = None
        self._route_generation = 0
        self._playback_generation = 0
        self._overflow_count = 0
        self._confirm_sent = False
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
            work = self._queue
        return work.qsize() if work is not None else 0

    @property
    def overflow_count(self) -> int:
        with self._lock:
            return self._overflow_count

    def metrics(self) -> AudioProcessingMetrics | None:
        with self._lock:
            processor = self._processor
        return processor.metrics() if processor is not None else None

    def start(
        self,
        monitor_generation: int,
        route_generation: int,
        playback_generation: int,
        confirm_sink: ConfirmSink,
        failure_sink: FailureSink,
    ) -> None:
        if min(monitor_generation, route_generation, playback_generation) <= 0:
            raise ValueError("barge-in generations must be positive")
        route = self._supervisor.current_route()
        if (
            route.state is not AudioRouteState.READY
            or route.input_device is None
            or route.route_generation != route_generation
        ):
            raise AudioProcessingUnavailable(
                "barge_in_route_unavailable",
                "当前麦克风路由不能启动声学插话",
            )
        with self._lock:
            if self._monitor_generation is not None:
                raise RuntimeError("barge-in monitor is already active")
        device_index = self._supervisor.registry.device_index(
            route.input_device.opaque_device_id,
            route.input_preference.direction,
        )
        delay_ms = _route_delay_ms(route)
        processor = self._processor_factory(delay_ms)
        capture = PyAudioCaptureAdapter(input_device_index=device_index)
        work: queue.Queue[object] = queue.Queue(maxsize=self._queue_capacity)
        stop_event = threading.Event()
        with self._lock:
            self._capture = capture
            self._processor = processor
            self._queue = work
            self._stop_event = stop_event
            self._monitor_generation = monitor_generation
            self._route_generation = route_generation
            self._playback_generation = playback_generation
            self._overflow_count = 0
            self._confirm_sent = False

        def capture_sink(frame: PcmFrame) -> bool:
            return self._offer(_CaptureWork(frame))

        worker = threading.Thread(
            target=self._worker_main,
            args=(
                monitor_generation,
                route_generation,
                playback_generation,
                work,
                stop_event,
                processor,
                confirm_sink,
                failure_sink,
            ),
            name=f"assistant-barge-in-worker-{monitor_generation}",
            daemon=True,
        )
        with self._lock:
            self._worker = worker
        worker.start()
        try:
            capture.start(monitor_generation, capture_sink)
        except Exception:
            self.stop()
            raise

    def offer_render(self, chunk: RenderReferenceChunk) -> bool:
        with self._lock:
            if (
                self._monitor_generation is None
                or chunk.playback_generation != self._playback_generation
            ):
                return False
        return self._offer(_RenderWork(chunk))

    def stop(self) -> None:
        with self._lock:
            generation = self._monitor_generation
            capture = self._capture
            work = self._queue
            stop_event = self._stop_event
            worker = self._worker
            processor = self._processor
            self._monitor_generation = None
            self._capture = None
            self._stop_event = None
        if stop_event is not None:
            stop_event.set()
        if capture is not None and generation is not None:
            try:
                capture.stop(generation)
            except Exception:
                capture.close()
        if work is not None:
            try:
                work.put_nowait(self._sentinel)
            except queue.Full:
                try:
                    work.get_nowait()
                    work.put_nowait(self._sentinel)
                except (queue.Empty, queue.Full):
                    pass
        if worker is not None and worker is not threading.current_thread():
            worker.join(timeout=2.0)
        worker_alive = bool(worker and worker.is_alive())
        if processor is not None and not worker_alive:
            processor.close()
        if work is not None and not worker_alive:
            while True:
                try:
                    work.get_nowait()
                except queue.Empty:
                    break
        with self._lock:
            self._worker = worker if worker_alive else None
            self._processor = processor if worker_alive else None
            self._queue = work if worker_alive else None
            if not worker_alive:
                self._route_generation = 0
                self._playback_generation = 0
        if worker_alive:
            raise AudioProcessingUnavailable(
                "barge_in_worker_stop_timeout",
                "声学插话 worker 未在时限内停止",
            )

    def _offer(self, value: object) -> bool:
        with self._lock:
            work = self._queue
            active = self._monitor_generation is not None
        if not active or work is None:
            return False
        try:
            work.put_nowait(value)
            return True
        except queue.Full:
            try:
                work.get_nowait()
            except queue.Empty:
                return False
            with self._lock:
                self._overflow_count += 1
            try:
                work.put_nowait(value)
                return True
            except queue.Full:
                return False

    def _worker_main(
        self,
        monitor_generation: int,
        route_generation: int,
        playback_generation: int,
        work: queue.Queue[object],
        stop_event: threading.Event,
        processor: WebRtcApmAudioProcessor,
        confirm_sink: ConfirmSink,
        failure_sink: FailureSink,
    ) -> None:
        vad = EnergyVoiceActivityDetector(
            EnergyVadConfig(
                warmup_ms=600,
                min_speech_ms=160,
                end_silence_ms=900,
                no_speech_timeout_ms=60_000,
                min_rms_threshold=12.0,
                min_peak_threshold=80,
                rms_noise_multiplier=1.45,
                peak_noise_multiplier=1.35,
                speech_trigger_frames=6,
            )
        )
        vad.reset(monitor_generation)
        pre_roll: deque[PcmFrame] = deque(maxlen=PRE_ROLL_FRAMES)
        render_sequence = 0
        try:
            while not stop_event.is_set():
                try:
                    value = work.get(timeout=0.1)
                except queue.Empty:
                    continue
                if value is self._sentinel:
                    break
                if isinstance(value, _RenderWork):
                    normalized = _normalize_to_mono_16k_20ms(
                        value.chunk.payload,
                        value.chunk.pcm_format.sample_rate_hz,
                        value.chunk.pcm_format.channels,
                    )
                    for block in _split_10_ms(normalized):
                        processor.process_render(
                            TimedPcmFrame(
                                route_generation=route_generation,
                                stream_generation=playback_generation,
                                sequence=render_sequence,
                                monotonic_ns=value.chunk.rendered_at_ns,
                                audio_format=PROCESSING_FORMAT_10_MS,
                                pcm16_le=block,
                            )
                        )
                        render_sequence += 1
                    continue
                if not isinstance(value, _CaptureWork):
                    continue
                processed_blocks: list[bytes] = []
                for block_index, block in enumerate(_split_10_ms(value.frame.pcm16_le)):
                    processed = processor.process_capture(
                        TimedPcmFrame(
                            route_generation=route_generation,
                            stream_generation=monitor_generation,
                            sequence=value.frame.sequence * 2 + block_index,
                            monotonic_ns=value.frame.captured_at_ns,
                            audio_format=PROCESSING_FORMAT_10_MS,
                            pcm16_le=block,
                        )
                    )
                    processed_blocks.append(processed.pcm16_le)
                processed_frame = PcmFrame(
                    generation=monitor_generation,
                    sequence=value.frame.sequence,
                    captured_at_ns=value.frame.captured_at_ns,
                    pcm16_le=b"".join(processed_blocks),
                )
                processed_frame.validate()
                pre_roll.append(processed_frame)
                snapshot = vad.observe(processed_frame)
                if (
                    snapshot.state is VoiceActivityState.SPEECH_DETECTED
                    and processor.metrics().state is ProcessingState.READY
                ):
                    with self._lock:
                        if self._confirm_sent:
                            continue
                        self._confirm_sent = True
                    confirm_sink(
                        monitor_generation,
                        playback_generation,
                        tuple(pre_roll),
                    )
        except Exception as exc:
            code = str(getattr(exc, "code", "barge_in_processing_failed"))
            failure_sink(monitor_generation, playback_generation, code)
            stop_event.set()


RuntimeFactory = Callable[[AudioSessionSupervisor], BargeInMonitorRuntimePort]


class AcousticBargeInCoordinator:
    """Start only during playback and promote one confirmed processed monitor turn."""

    def __init__(
        self,
        controller: "AssistantController",
        supervisor: AudioSessionSupervisor,
        audio_engine: AssistantAudioEngine,
        playback_coordinator: PlaybackCoordinator,
        *,
        runtime_factory: RuntimeFactory = LocalBargeInMonitorRuntime,
    ) -> None:
        self._controller = controller
        self._supervisor = supervisor
        self._audio_engine = audio_engine
        self._playback_coordinator = playback_coordinator
        self._runtime_factory = runtime_factory
        module_available = importlib.util.find_spec("aec_audio_processing") is not None
        self._snapshot = AcousticBargeInSnapshot(available=module_available)
        self._runtime: BargeInMonitorRuntimePort | None = None
        self._listeners: set[SnapshotListener] = set()
        self._generation = 0
        self._loop: asyncio.AbstractEventLoop | None = None
        self._operation_lock = asyncio.Lock()
        self._reconcile_task: asyncio.Task[None] | None = None
        self._operation_tasks: set[asyncio.Task[None]] = set()
        self._reconcile_requested = False
        self._failed_context: tuple[int, int] | None = None
        self._unsubscribe_state: Callable[[], None] | None = None
        self._unsubscribe_audio: Callable[[], None] | None = None
        self._unsubscribe_lease: Callable[[], None] | None = None
        self._started = False
        self._closed = False

    @property
    def snapshot(self) -> AcousticBargeInSnapshot:
        runtime = self._runtime
        if runtime is None:
            return self._snapshot
        metrics = runtime.metrics()
        return replace(
            self._snapshot,
            monitor_active=runtime.active,
            worker_alive=runtime.worker_alive,
            capture_queue_size=runtime.queue_size,
            queue_overflow_count=runtime.overflow_count,
            processing_state=(metrics.state.value if metrics else "warming"),
            aec_effective=bool(metrics and metrics.aec_effective),
            ns_effective=bool(metrics and metrics.ns_effective),
            agc_effective=bool(metrics and metrics.agc_effective),
            stream_delay_ms=(metrics.estimated_delay_ms if metrics else None),
            render_frames=(metrics.render_frames if metrics else 0),
            capture_frames=(metrics.capture_frames if metrics else 0),
            processed_frames=(metrics.processed_frames if metrics else 0),
        )

    def subscribe(self, listener: SnapshotListener) -> Callable[[], None]:
        self._listeners.add(listener)

        def unsubscribe() -> None:
            self._listeners.discard(listener)

        return unsubscribe

    async def start(self) -> None:
        if self._closed:
            raise RuntimeError("acoustic barge-in coordinator is closed")
        if self._started:
            return
        self._loop = asyncio.get_running_loop()
        self._unsubscribe_state = self._controller.subscribe(self._on_state)
        self._unsubscribe_audio = self._supervisor.subscribe(self._on_audio)
        self._unsubscribe_lease = self._supervisor.microphone_coordinator.subscribe(self._on_lease)
        self._supervisor.microphone_coordinator.bind_barge_in_yield_handler(
            self.yield_to_assistant_capture
        )
        self._playback_coordinator.bind_render_reference_sink(self.offer_render_reference)
        self._started = True
        await self.reconcile()

    async def reconcile(self) -> None:
        if self._closed:
            return
        async with self._operation_lock:
            desired, status = self._desired_running()
            playback_generation = self._controller.state.audio.playback_generation
            route_generation = self._supervisor.snapshot.route_generation
            if self._runtime is not None and (
                not desired
                or self._snapshot.playback_generation != playback_generation
                or self._snapshot.route_generation != route_generation
            ):
                await self._stop_runtime(release_lease=True, status=status)
            if desired and self._runtime is None:
                context = (playback_generation, route_generation)
                if self._failed_context == context:
                    self._snapshot = replace(self._snapshot, status="unavailable")
                    self._notify()
                else:
                    await self._start_runtime(playback_generation, route_generation)
            elif not desired and self._runtime is None:
                if not self._controller.state.conversation.streaming_barge_in_enabled:
                    self._failed_context = None
                self._snapshot = replace(
                    self._snapshot,
                    enabled=self._controller.state.conversation.streaming_barge_in_enabled,
                    status=status,
                    monitor_active=False,
                    worker_alive=False,
                    capture_queue_size=0,
                )
                self._notify()

    def offer_render_reference(
        self,
        playback_generation: int,
        pcm_format: PcmAudioFormat,
        payload: bytes,
        rendered_at_ns: int,
    ) -> None:
        runtime = self._runtime
        if runtime is None:
            return
        runtime.offer_render(
            RenderReferenceChunk(
                playback_generation=playback_generation,
                pcm_format=pcm_format,
                payload=bytes(payload),
                rendered_at_ns=rendered_at_ns,
            )
        )

    async def yield_to_assistant_capture(self) -> None:
        if self._closed:
            return
        async with self._operation_lock:
            await self._stop_runtime(
                release_lease=True,
                status="paused_for_assistant",
            )

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._reconcile_requested = False
        task = self._reconcile_task
        self._reconcile_task = None
        if task is not None and task is not asyncio.current_task() and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        operation_tasks = tuple(task for task in self._operation_tasks if not task.done())
        for operation_task in operation_tasks:
            operation_task.cancel()
        if operation_tasks:
            await asyncio.gather(*operation_tasks, return_exceptions=True)
        self._operation_tasks.clear()
        async with self._operation_lock:
            await self._stop_runtime(release_lease=True, status="closed")
        self._playback_coordinator.bind_render_reference_sink(None)
        self._supervisor.microphone_coordinator.bind_barge_in_yield_handler(None)
        for unsubscribe in (
            self._unsubscribe_state,
            self._unsubscribe_audio,
            self._unsubscribe_lease,
        ):
            if unsubscribe is not None:
                unsubscribe()
        self._unsubscribe_state = None
        self._unsubscribe_audio = None
        self._unsubscribe_lease = None
        self._listeners.clear()
        self._started = False

    def diagnostics(self) -> dict[str, object]:
        result = self.snapshot.public_dict()
        task = self._reconcile_task
        tasks = [task.get_name() for task in self._operation_tasks if not task.done()]
        if task is not None and not task.done():
            tasks.append(task.get_name())
        result.update(
            {
                "pending_tasks": sorted(tasks),
                "microphone_owner": self._supervisor.microphone_coordinator.owner.value,
                "second_python_process": 0,
            }
        )
        return result

    async def _start_runtime(self, playback_generation: int, route_generation: int) -> None:
        generation = self._generation + 1
        acquired = await self._supervisor.microphone_coordinator.acquire(
            generation,
            MicrophoneOwner.BARGE_IN_MONITOR,
            route_generation,
        )
        if not acquired:
            self._snapshot = replace(self._snapshot, status="paused_microphone_busy")
            self._notify()
            return
        runtime: BargeInMonitorRuntimePort | None = None
        try:
            runtime = self._runtime_factory(self._supervisor)
            loop = self._loop or asyncio.get_running_loop()

            def confirmed(
                monitor_generation: int,
                confirmed_playback_generation: int,
                pre_roll: tuple[PcmFrame, ...],
            ) -> None:
                loop.call_soon_threadsafe(
                    self._schedule_confirm,
                    monitor_generation,
                    confirmed_playback_generation,
                    pre_roll,
                )

            def failed(
                monitor_generation: int,
                failed_playback_generation: int,
                code: str,
            ) -> None:
                loop.call_soon_threadsafe(
                    self._schedule_failure,
                    monitor_generation,
                    failed_playback_generation,
                    code,
                )

            await asyncio.to_thread(
                runtime.start,
                generation,
                route_generation,
                playback_generation,
                confirmed,
                failed,
            )
        except Exception as exc:
            if runtime is not None:
                try:
                    await asyncio.to_thread(runtime.stop)
                except Exception:
                    pass
            await self._supervisor.microphone_coordinator.release(
                generation,
                MicrophoneOwner.BARGE_IN_MONITOR,
                route_generation,
            )
            code = str(getattr(exc, "code", "barge_in_start_failed"))
            self._supervisor.set_processing_state(ProcessingState.FAILED)
            self._snapshot = replace(
                self._snapshot,
                enabled=True,
                available=False,
                status="unavailable",
                error_code=code,
            )
            self._failed_context = (playback_generation, route_generation)
            self._notify()
            return
        self._runtime = runtime
        self._failed_context = None
        self._generation = generation
        self._supervisor.set_capture_activity(CaptureActivity.BARGE_IN_MONITOR)
        self._supervisor.set_processing_state(ProcessingState.WARMING)
        self._snapshot = replace(
            self._snapshot,
            enabled=True,
            available=True,
            status="monitoring",
            monitor_generation=generation,
            playback_generation=playback_generation,
            route_generation=route_generation,
            processing_state="warming",
            monitor_active=True,
            worker_alive=True,
            error_code=None,
        )
        self._notify()

    async def _stop_runtime(self, *, release_lease: bool, status: str) -> None:
        runtime = self._runtime
        generation = self._snapshot.monitor_generation
        route_generation = self._snapshot.route_generation
        self._runtime = None
        stop_error: Exception | None = None
        metrics = runtime.metrics() if runtime is not None else None
        if runtime is not None:
            try:
                await asyncio.to_thread(runtime.stop)
            except Exception as exc:
                stop_error = exc
        if release_lease and generation > 0:
            await self._supervisor.microphone_coordinator.release(
                generation,
                MicrophoneOwner.BARGE_IN_MONITOR,
                route_generation,
            )
        if self._supervisor.snapshot.capture_activity is CaptureActivity.BARGE_IN_MONITOR:
            self._supervisor.set_capture_activity(CaptureActivity.INACTIVE)
        self._supervisor.set_processing_state(
            ProcessingState.FAILED if stop_error else ProcessingState.BYPASS
        )
        self._snapshot = replace(
            self._snapshot,
            status="error" if stop_error else status,
            monitor_active=False,
            worker_alive=False,
            capture_queue_size=0,
            queue_overflow_count=(runtime.overflow_count if runtime else 0),
            render_frames=(metrics.render_frames if metrics else self._snapshot.render_frames),
            capture_frames=(metrics.capture_frames if metrics else self._snapshot.capture_frames),
            processed_frames=(
                metrics.processed_frames if metrics else self._snapshot.processed_frames
            ),
            processing_state=(metrics.state.value if metrics else "bypass"),
            aec_effective=bool(metrics and metrics.aec_effective),
            ns_effective=bool(metrics and metrics.ns_effective),
            agc_effective=bool(metrics and metrics.agc_effective),
            stream_delay_ms=(metrics.estimated_delay_ms if metrics else None),
            error_code=(
                str(getattr(stop_error, "code", "barge_in_stop_failed"))
                if stop_error
                else self._snapshot.error_code
            ),
        )
        self._notify()

    def _schedule_confirm(
        self,
        monitor_generation: int,
        playback_generation: int,
        pre_roll: tuple[PcmFrame, ...],
    ) -> None:
        self._track_operation_task(
            asyncio.create_task(
                self._handle_confirm(monitor_generation, playback_generation, pre_roll),
                name=f"assistant-barge-in-confirm-{monitor_generation}",
            )
        )

    async def _handle_confirm(
        self,
        monitor_generation: int,
        playback_generation: int,
        pre_roll: tuple[PcmFrame, ...],
    ) -> None:
        async with self._operation_lock:
            if (
                self._runtime is None
                or monitor_generation != self._snapshot.monitor_generation
                or playback_generation != self._snapshot.playback_generation
                or not self._confirmation_still_valid(playback_generation)
            ):
                return
            next_capture_generation = self._controller.state.audio.capture_generation + 1
            route_generation = self._snapshot.route_generation
            self._snapshot = replace(
                self._snapshot,
                candidate_count=self._snapshot.candidate_count + 1,
                status="confirming",
            )
            await self._stop_runtime(release_lease=False, status="handoff")
            transferred = await self._supervisor.microphone_coordinator.transfer(
                generation=monitor_generation,
                expected_owner=MicrophoneOwner.BARGE_IN_MONITOR,
                next_owner=MicrophoneOwner.ASSISTANT_CAPTURE,
                next_generation=next_capture_generation,
                route_generation=route_generation,
            )
            if not transferred:
                await self._supervisor.microphone_coordinator.release(
                    monitor_generation,
                    MicrophoneOwner.BARGE_IN_MONITOR,
                    route_generation,
                )
                self._schedule_reconcile()
                return
            staged = tuple(pre_roll[-PRE_ROLL_FRAMES:])
            try:
                self._audio_engine.stage_processed_pre_roll(
                    next_capture_generation,
                    staged,
                )
            except Exception:
                await self._supervisor.microphone_coordinator.release(
                    next_capture_generation,
                    MicrophoneOwner.ASSISTANT_CAPTURE,
                    route_generation,
                )
                self._snapshot = replace(
                    self._snapshot,
                    status="error",
                    error_code="barge_in_pre_roll_stage_failed",
                )
                self._notify()
                return
            self._snapshot = replace(
                self._snapshot,
                confirmed_count=self._snapshot.confirmed_count + 1,
                pre_roll_frames_staged=len(staged),
                status="handoff",
            )
            self._notify()
        try:
            await self._controller.confirm_acoustic_barge_in(
                playback_generation=playback_generation,
                monitor_generation=monitor_generation,
                next_capture_generation=next_capture_generation,
            )
        except Exception as exc:
            self._audio_engine.clear_staged_pre_roll(next_capture_generation)
            await self._supervisor.microphone_coordinator.release(
                next_capture_generation,
                MicrophoneOwner.ASSISTANT_CAPTURE,
                route_generation,
            )
            self._snapshot = replace(
                self._snapshot,
                status="error",
                error_code=str(getattr(exc, "code", "barge_in_promotion_failed")),
            )
            self._notify()
            self._schedule_reconcile()
            return
        state = self._controller.state
        accepted = bool(
            state.audio.capture_generation == next_capture_generation
            and state.conversation.streaming_session_active
            and state.conversation.barge_in_trigger_count >= self._snapshot.confirmed_count
        )
        if not accepted:
            self._audio_engine.clear_staged_pre_roll(next_capture_generation)
            await self._supervisor.microphone_coordinator.release(
                next_capture_generation,
                MicrophoneOwner.ASSISTANT_CAPTURE,
                self._snapshot.route_generation,
            )
        else:
            self._snapshot = replace(
                self._snapshot,
                status="promoted",
                playback_cancel_count=self._snapshot.playback_cancel_count + 1,
                abort_count=self._snapshot.abort_count + 1,
            )
            self._notify()
        self._schedule_reconcile()

    def _schedule_failure(
        self,
        monitor_generation: int,
        playback_generation: int,
        code: str,
    ) -> None:
        self._track_operation_task(
            asyncio.create_task(
                self._handle_failure(monitor_generation, playback_generation, code),
                name=f"assistant-barge-in-failure-{monitor_generation}",
            )
        )

    async def _handle_failure(
        self,
        monitor_generation: int,
        playback_generation: int,
        code: str,
    ) -> None:
        async with self._operation_lock:
            if (
                monitor_generation != self._snapshot.monitor_generation
                or playback_generation != self._snapshot.playback_generation
            ):
                return
            await self._stop_runtime(release_lease=True, status="error")
            self._snapshot = replace(
                self._snapshot,
                available=False,
                status="unavailable",
                error_code=code,
            )
            self._failed_context = (
                playback_generation,
                self._snapshot.route_generation,
            )
            self._notify()

    def _track_operation_task(self, task: asyncio.Task[None]) -> None:
        self._operation_tasks.add(task)
        task.add_done_callback(self._operation_tasks.discard)

    def _desired_running(self) -> tuple[bool, str]:
        state = self._controller.state
        audio = self._supervisor.snapshot
        enabled = state.conversation.streaming_barge_in_enabled
        if not enabled:
            return False, "disabled"
        if not state.enabled or not state.is_connected:
            return False, "paused_disconnected"
        if not state.conversation.streaming_session_active:
            return False, "waiting_for_session"
        if state.phase not in {AssistantPhase.THINKING, AssistantPhase.SPEAKING}:
            return False, "waiting_for_playback"
        if state.audio.status not in {AssistantAudioStatus.IDLE, AssistantAudioStatus.PLAYING}:
            return False, "paused_capture"
        if audio.route_state is not AudioRouteState.READY:
            return False, "paused_route"
        if audio.playback_activity not in {
            PlaybackActivity.BUFFERING,
            PlaybackActivity.PLAYING,
            PlaybackActivity.DRAINING,
        }:
            return False, "waiting_for_playback"
        if audio.capture_activity not in {
            CaptureActivity.INACTIVE,
            CaptureActivity.BARGE_IN_MONITOR,
        }:
            return False, "paused_capture"
        owner = self._supervisor.microphone_coordinator.owner
        if owner not in {MicrophoneOwner.NONE, MicrophoneOwner.BARGE_IN_MONITOR}:
            return False, "paused_microphone_busy"
        return True, "monitoring"

    def _confirmation_still_valid(self, playback_generation: int) -> bool:
        state = self._controller.state
        return bool(
            state.enabled
            and state.is_connected
            and state.conversation.streaming_barge_in_enabled
            and state.conversation.streaming_session_active
            and state.audio.playback_generation == playback_generation
            and state.audio.status is AssistantAudioStatus.PLAYING
            and self._supervisor.snapshot.playback_activity
            in {PlaybackActivity.PLAYING, PlaybackActivity.DRAINING}
        )

    def _on_state(self, _state) -> None:
        self._schedule_reconcile()

    def _on_audio(self, _snapshot) -> None:
        self._schedule_reconcile()

    def _on_lease(self) -> None:
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
        self._reconcile_requested = True
        task = self._reconcile_task
        if task is not None and not task.done():
            return
        task = asyncio.create_task(
            self._reconcile_until_stable(),
            name="assistant-barge-in-reconcile",
        )
        self._reconcile_task = task

        def completed(done: asyncio.Task[None]) -> None:
            if self._reconcile_task is done:
                self._reconcile_task = None

        task.add_done_callback(completed)

    async def _reconcile_until_stable(self) -> None:
        while self._reconcile_requested and not self._closed:
            self._reconcile_requested = False
            await self.reconcile()
            await asyncio.sleep(0)

    def _notify(self) -> None:
        snapshot = self.snapshot
        for listener in tuple(self._listeners):
            try:
                listener(snapshot)
            except Exception:
                continue


def _route_delay_ms(route) -> int:
    input_ms = float(route.input_device.reported_input_latency_ms or 0.0)
    output_ms = float(route.output_device.reported_output_latency_ms or 0.0)
    return max(0, min(500, round(input_ms + output_ms)))


def _split_10_ms(payload: bytes) -> tuple[bytes, bytes]:
    if len(payload) != MONITOR_FORMAT_20_MS.bytes_per_frame:
        raise ValueError("barge-in PCM must be one 20 ms mono/16 kHz frame")
    middle = PROCESSING_FORMAT_10_MS.bytes_per_frame
    return payload[:middle], payload[middle:]


def _normalize_to_mono_16k_20ms(
    payload: bytes,
    sample_rate_hz: int,
    channels: int,
) -> bytes:
    if sample_rate_hz <= 0 or channels <= 0 or len(payload) % (2 * channels):
        raise ValueError("invalid render reference PCM format")
    source_frames = len(payload) // (2 * channels)
    if source_frames <= 1:
        return b"\x00" * MONITOR_FORMAT_20_MS.bytes_per_frame
    samples = struct.unpack("<" + "h" * (source_frames * channels), payload)
    mono = [
        sum(samples[index * channels : (index + 1) * channels]) / channels
        for index in range(source_frames)
    ]
    target_frames = MONITOR_FORMAT_20_MS.samples_per_frame
    scale = (source_frames - 1) / max(1, target_frames - 1)
    output: list[int] = []
    for target_index in range(target_frames):
        position = target_index * scale
        left = int(position)
        right = min(source_frames - 1, left + 1)
        fraction = position - left
        value = mono[left] * (1.0 - fraction) + mono[right] * fraction
        output.append(max(-32768, min(32767, round(value))))
    return struct.pack("<" + "h" * len(output), *output)
