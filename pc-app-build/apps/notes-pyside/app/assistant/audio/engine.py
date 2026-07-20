"""Shared single-capture audio engine for PTT and streaming conversation."""

from __future__ import annotations

import asyncio
import queue
import struct
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace

from .models import (
    ENCODED_PACKET_CAPACITY,
    PCM_INGRESS_CAPACITY,
    AudioCaptureSummary,
    EncodedAudioPacket,
    PcmFrame,
    VoiceActivitySnapshot,
)
from .ports import AudioCapturePort, OpusEncoderPort, VoiceActivityDetectorPort
from ..state import VoiceActivityState
from .vad import EnergyVadConfig, EnergyVoiceActivityDetector
from .gate6_contracts import MicrophoneOwner
from .queues import (
    AudioQueueClosed,
    AudioQueueOverflow,
    DropOldestAudioQueue,
    FailOnOverflowAudioQueue,
)

EncoderFactory = Callable[[], OpusEncoderPort]
VadFactory = Callable[[int], VoiceActivityDetectorPort]


class AudioEngineBusyError(RuntimeError):
    pass


class AudioEngineGenerationError(RuntimeError):
    pass


class AudioEngineFailure(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(slots=True)
class _Metrics:
    captured_frames: int = 0
    encoded_frames: int = 0
    uploaded_frames: int = 0
    dropped_pcm_frames: int = 0
    uplink_overflow_count: int = 0
    stale_frame_count: int = 0
    speech_seen: bool = False
    first_pcm_at_ns: int | None = None
    first_opus_at_ns: int | None = None
    first_opus_upload_at_ns: int | None = None


class MicrophoneLeaseCoordinator:
    """Owner-aware process-wide microphone lease with generation-safe transfer."""

    def __init__(
        self,
        route_generation_provider: Callable[[], int] | None = None,
    ) -> None:
        self._generation: int | None = None
        self._owner = MicrophoneOwner.NONE
        self._route_generation = 0
        self._route_generation_provider = route_generation_provider
        self._lock = asyncio.Lock()
        self._wakeword_yield_handler: Callable[[], Awaitable[None]] | None = None
        self._listeners: set[Callable[[], None]] = set()

    @property
    def generation(self) -> int | None:
        return self._generation

    @property
    def owner(self) -> MicrophoneOwner:
        return self._owner

    @property
    def route_generation(self) -> int:
        return self._route_generation

    async def acquire(
        self,
        generation: int,
        owner: MicrophoneOwner = MicrophoneOwner.ASSISTANT_CAPTURE,
        route_generation: int | None = None,
    ) -> bool:
        if route_generation is None:
            provider = self._route_generation_provider
            route_generation = int(provider()) if provider is not None else 0
        if generation < 0 or route_generation < 0:
            raise ValueError("lease generations cannot be negative")
        if owner is MicrophoneOwner.NONE:
            raise ValueError("NONE cannot acquire the microphone")
        async with self._lock:
            if (
                self._generation == generation
                and self._owner is owner
                and self._route_generation == route_generation
            ):
                return True
            should_yield_wakeword = (
                owner is MicrophoneOwner.ASSISTANT_CAPTURE
                and self._owner is MicrophoneOwner.WAKEWORD_KWS
                and self._wakeword_yield_handler is not None
            )
            yield_handler = self._wakeword_yield_handler if should_yield_wakeword else None
            if self._generation is not None and yield_handler is None:
                return False
        if yield_handler is not None:
            await yield_handler()
        async with self._lock:
            if (
                self._generation == generation
                and self._owner is owner
                and self._route_generation == route_generation
            ):
                return True
            if self._generation is not None:
                return False
            self._generation = generation
            self._owner = owner
            self._route_generation = route_generation
        self._notify_listeners()
        return True

    def subscribe(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.add(listener)

        def unsubscribe() -> None:
            self._listeners.discard(listener)

        return unsubscribe

    def bind_wakeword_yield_handler(
        self,
        handler: Callable[[], Awaitable[None]] | None,
    ) -> None:
        """Bind the only in-process KWS preemption hook.

        The callback executes outside the coordinator lock so it may stop the
        KWS stream and release its generation without deadlocking.
        """

        self._wakeword_yield_handler = handler

    async def release(
        self,
        generation: int,
        owner: MicrophoneOwner | None = None,
        route_generation: int | None = None,
    ) -> bool:
        async with self._lock:
            if self._generation != generation:
                return False
            if owner is not None and self._owner is not owner:
                return False
            if route_generation is not None and self._route_generation != route_generation:
                return False
            self._generation = None
            self._owner = MicrophoneOwner.NONE
            self._route_generation = 0
        self._notify_listeners()
        return True

    async def transfer(
        self,
        *,
        generation: int,
        expected_owner: MicrophoneOwner,
        next_owner: MicrophoneOwner,
        next_generation: int,
        route_generation: int,
    ) -> bool:
        if next_owner is MicrophoneOwner.NONE:
            raise ValueError("transfer target cannot be NONE")
        if min(next_generation, route_generation) < 0:
            raise ValueError("lease generations cannot be negative")
        async with self._lock:
            if self._generation != generation or self._owner is not expected_owner:
                return False
            self._generation = next_generation
            self._owner = next_owner
            self._route_generation = route_generation
        self._notify_listeners()
        return True

    async def force_release(self) -> None:
        async with self._lock:
            changed = self._generation is not None or self._owner is not MicrophoneOwner.NONE
            self._generation = None
            self._owner = MicrophoneOwner.NONE
            self._route_generation = 0
        if changed:
            self._notify_listeners()

    def public_dict(self) -> dict[str, object]:
        return {
            "owner": self._owner.value,
            "lease_generation": self._generation,
            "route_generation": self._route_generation,
        }

    def _notify_listeners(self) -> None:
        for listener in tuple(self._listeners):
            try:
                listener()
            except Exception:
                continue


class AssistantAudioEngine:
    """Own one capture adapter, one worker, and one encoded packet queue."""

    def __init__(
        self,
        *,
        capture: AudioCapturePort,
        encoder_factory: EncoderFactory,
        pcm_capacity: int = PCM_INGRESS_CAPACITY,
        packet_capacity: int = ENCODED_PACKET_CAPACITY,
        speech_peak_threshold: int = 500,
        vad_factory: VadFactory | None = None,
        vad_event_capacity: int = 32,
    ) -> None:
        self._capture = capture
        self._encoder_factory = encoder_factory
        self._pcm_capacity = int(pcm_capacity)
        self._packet_capacity = int(packet_capacity)
        self._speech_peak_threshold = int(speech_peak_threshold)
        self._vad_factory = vad_factory or (
            lambda timeout_ms: EnergyVoiceActivityDetector(
                EnergyVadConfig(no_speech_timeout_ms=timeout_ms)
            )
        )
        self._vad_event_capacity = int(vad_event_capacity)
        self._state_lock = threading.RLock()
        self._active_generation: int | None = None
        self._started_at_ns: int | None = None
        self._pcm_queue: DropOldestAudioQueue[PcmFrame] | None = None
        self._packet_queue: FailOnOverflowAudioQueue[EncodedAudioPacket] | None = None
        self._vad_queue: DropOldestAudioQueue[VoiceActivitySnapshot] | None = None
        self._vad: VoiceActivityDetectorPort | None = None
        self._last_vad_state: VoiceActivityState | None = None
        self._worker: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._worker_done: threading.Event | None = None
        self._failure: AudioEngineFailure | None = None
        self._metrics = _Metrics()
        self._closed = False

    @property
    def active_generation(self) -> int | None:
        with self._state_lock:
            return self._active_generation

    @property
    def is_active(self) -> bool:
        return self.active_generation is not None

    @property
    def worker_alive(self) -> bool:
        with self._state_lock:
            worker = self._worker
        return worker is not None and worker.is_alive()

    @property
    def input_device_public_name(self) -> str | None:
        return self._capture.input_device_public_name

    @property
    def failure(self) -> AudioEngineFailure | None:
        with self._state_lock:
            return self._failure

    async def start_capture(
        self,
        generation: int,
        *,
        requested_at_ns: int,
        vad_enabled: bool = False,
        vad_idle_timeout_ms: int = 8_000,
    ) -> None:
        if generation < 0:
            raise ValueError("capture generation cannot be negative")
        with self._state_lock:
            if self._closed:
                raise RuntimeError("audio engine is closed")
            if self._active_generation is not None:
                raise AudioEngineBusyError("one audio capture is already active")
            self._active_generation = generation
            self._started_at_ns = requested_at_ns
            self._pcm_queue = DropOldestAudioQueue(self._pcm_capacity)
            self._packet_queue = FailOnOverflowAudioQueue(self._packet_capacity)
            self._vad_queue = (
                DropOldestAudioQueue(self._vad_event_capacity) if vad_enabled else None
            )
            self._vad = self._vad_factory(int(vad_idle_timeout_ms)) if vad_enabled else None
            if self._vad is not None:
                self._vad.reset(generation)
            self._last_vad_state = None
            self._stop_event = threading.Event()
            self._worker_done = threading.Event()
            self._failure = None
            self._metrics = _Metrics()
            self._worker = threading.Thread(
                target=self._worker_main,
                args=(generation,),
                name=f"assistant-audio-worker-{generation}",
                daemon=True,
            )
            self._worker.start()
        try:
            await asyncio.to_thread(self._capture.start, generation, self._accept_frame)
        except Exception:
            await self.cancel_capture(generation, reason="capture_start_failed")
            raise

    async def next_packet(self, generation: int) -> EncodedAudioPacket | None:
        while True:
            with self._state_lock:
                packet_queue = self._packet_queue
                worker_done = self._worker_done
                failure = self._failure
                active_generation = self._active_generation
            if failure is not None:
                raise failure
            if packet_queue is None:
                return None
            if active_generation not in {None, generation}:
                return None
            try:
                packet = await asyncio.to_thread(packet_queue.get, 0.05)
            except queue.Empty:
                if worker_done is not None and worker_done.is_set() and len(packet_queue) == 0:
                    failure = self.failure
                    if failure is not None:
                        raise failure
                    return None
                continue
            except AudioQueueClosed:
                failure = self.failure
                if failure is not None:
                    raise failure
                return None
            if packet.generation != generation:
                with self._state_lock:
                    self._metrics.stale_frame_count += 1
                continue
            return packet

    async def next_voice_activity(self, generation: int) -> VoiceActivitySnapshot | None:
        while True:
            with self._state_lock:
                vad_queue = self._vad_queue
                worker_done = self._worker_done
                failure = self._failure
                active_generation = self._active_generation
            if failure is not None:
                raise failure
            if vad_queue is None:
                return None
            if active_generation not in {None, generation}:
                return None
            try:
                snapshot = await asyncio.to_thread(vad_queue.get, 0.05)
            except queue.Empty:
                if worker_done is not None and worker_done.is_set() and len(vad_queue) == 0:
                    return None
                continue
            except AudioQueueClosed:
                return None
            if snapshot.generation != generation:
                with self._state_lock:
                    self._metrics.stale_frame_count += 1
                continue
            return snapshot

    def mark_uploaded(self, packet: EncodedAudioPacket, *, uploaded_at_ns: int) -> None:
        with self._state_lock:
            if packet.generation != self._active_generation:
                self._metrics.stale_frame_count += 1
                return
            self._metrics.uploaded_frames += 1
            if self._metrics.first_opus_upload_at_ns is None:
                self._metrics.first_opus_upload_at_ns = uploaded_at_ns

    async def stop_capture(
        self,
        generation: int,
        *,
        budget_seconds: float = 1.5,
    ) -> AudioCaptureSummary:
        started = time.perf_counter_ns()
        with self._state_lock:
            if self._active_generation is None:
                return self._summary(generation, stop_latency_ms=0, stopped_within_budget=True)
            if generation != self._active_generation:
                raise AudioEngineGenerationError(
                    "stop generation does not own the active audio capture"
                )
            stop_event = self._stop_event
            pcm_queue = self._pcm_queue
            worker = self._worker
        if stop_event is not None:
            stop_event.set()
        stopped_within_budget = True
        try:
            await asyncio.wait_for(
                asyncio.to_thread(self._capture.stop, generation),
                timeout=max(0.05, float(budget_seconds) * 0.55),
            )
        except asyncio.TimeoutError:
            stopped_within_budget = False
            self._set_failure(
                AudioEngineFailure(
                    "audio_capture_stop_timeout",
                    "microphone capture stop exceeded the bounded timeout",
                )
            )
        except Exception as exc:
            stopped_within_budget = False
            self._set_failure(
                AudioEngineFailure(
                    "audio_capture_stop_failed",
                    str(exc) or type(exc).__name__,
                )
            )
        finally:
            if pcm_queue is not None:
                pcm_queue.close()
        remaining = max(0.05, float(budget_seconds) - (time.perf_counter_ns() - started) / 1e9)
        if worker is not None and worker.is_alive():
            await asyncio.to_thread(worker.join, remaining)
            if worker.is_alive():
                stopped_within_budget = False
                self._set_failure(
                    AudioEngineFailure(
                        "audio_capture_stop_timeout",
                        "audio worker did not stop within the bounded timeout",
                    )
                )
        latency_ms = max(0, int((time.perf_counter_ns() - started) / 1_000_000))
        return self._summary(
            generation,
            stop_latency_ms=latency_ms,
            stopped_within_budget=stopped_within_budget,
        )

    async def cancel_capture(self, generation: int, *, reason: str) -> AudioCaptureSummary:
        try:
            summary = await self.stop_capture(generation, budget_seconds=1.0)
        except AudioEngineGenerationError:
            summary = self._summary(generation, stop_latency_ms=0, stopped_within_budget=False)
        with self._state_lock:
            packet_queue = self._packet_queue
            vad_queue = self._vad_queue
        if packet_queue is not None:
            packet_queue.drain()
        if vad_queue is not None:
            vad_queue.drain()
        return replace(summary, error_message=summary.error_message or reason)

    def current_summary(
        self,
        generation: int,
        *,
        stop_latency_ms: int = 0,
        stopped_within_budget: bool = True,
    ) -> AudioCaptureSummary:
        return self._summary(
            generation,
            stop_latency_ms=stop_latency_ms,
            stopped_within_budget=stopped_within_budget,
        )

    async def finish_generation(self, generation: int) -> None:
        with self._state_lock:
            if self._active_generation not in {None, generation}:
                return
            packet_queue = self._packet_queue
            pcm_queue = self._pcm_queue
            vad_queue = self._vad_queue
            self._active_generation = None
            self._started_at_ns = None
            self._worker = None
            self._stop_event = None
            self._worker_done = None
            self._pcm_queue = None
            self._packet_queue = None
            self._vad_queue = None
            self._vad = None
            self._last_vad_state = None
        if pcm_queue is not None:
            pcm_queue.close()
        if packet_queue is not None:
            packet_queue.close()
        if vad_queue is not None:
            vad_queue.close()

    async def close(self) -> None:
        with self._state_lock:
            if self._closed:
                return
            generation = self._active_generation
        if generation is not None:
            await self.cancel_capture(generation, reason="audio_engine_close")
            await self.finish_generation(generation)
        await asyncio.to_thread(self._capture.close)
        with self._state_lock:
            self._closed = True

    def _accept_frame(self, frame: PcmFrame) -> bool:
        with self._state_lock:
            if frame.generation != self._active_generation:
                self._metrics.stale_frame_count += 1
                return False
            pcm_queue = self._pcm_queue
            stop_event = self._stop_event
            if pcm_queue is None or stop_event is None or stop_event.is_set():
                self._metrics.stale_frame_count += 1
                return False
        try:
            frame.validate()
            dropped = pcm_queue.put(frame)
        except (AudioQueueClosed, ValueError, TypeError):
            return False
        with self._state_lock:
            self._metrics.captured_frames += 1
            if self._metrics.first_pcm_at_ns is None:
                self._metrics.first_pcm_at_ns = frame.captured_at_ns
            if dropped is not None:
                self._metrics.dropped_pcm_frames += 1
        return True

    def _worker_main(self, generation: int) -> None:
        encoder: OpusEncoderPort | None = None
        try:
            encoder = self._encoder_factory()
            while True:
                with self._state_lock:
                    pcm_queue = self._pcm_queue
                    packet_queue = self._packet_queue
                    stop_event = self._stop_event
                if pcm_queue is None or packet_queue is None or stop_event is None:
                    return
                try:
                    frame = pcm_queue.get(timeout=0.05)
                except queue.Empty:
                    if stop_event.is_set():
                        return
                    continue
                except AudioQueueClosed:
                    return
                if frame.generation != generation:
                    with self._state_lock:
                        self._metrics.stale_frame_count += 1
                    continue
                self._observe_speech(frame)
                self._observe_vad(frame)
                try:
                    packet = encoder.encode(frame)
                    packet.validate()
                    packet_queue.put(packet)
                except AudioQueueOverflow as exc:
                    with self._state_lock:
                        self._metrics.uplink_overflow_count += 1
                    self._set_failure(AudioEngineFailure("audio_uplink_overflow", str(exc)))
                    stop_event.set()
                    return
                except Exception as exc:
                    self._set_failure(
                        AudioEngineFailure(
                            "audio_encoder_failed",
                            str(exc) or type(exc).__name__,
                        )
                    )
                    stop_event.set()
                    return
                with self._state_lock:
                    self._metrics.encoded_frames += 1
                    if self._metrics.first_opus_at_ns is None:
                        self._metrics.first_opus_at_ns = packet.encoded_at_ns
        finally:
            if encoder is not None:
                try:
                    encoder.close()
                except Exception:
                    pass
            with self._state_lock:
                packet_queue = self._packet_queue
                vad_queue = self._vad_queue
                worker_done = self._worker_done
            if packet_queue is not None:
                packet_queue.close()
            if vad_queue is not None:
                vad_queue.close()
            if worker_done is not None:
                worker_done.set()

    def _observe_vad(self, frame: PcmFrame) -> None:
        with self._state_lock:
            detector = self._vad
            vad_queue = self._vad_queue
            previous = self._last_vad_state
        if detector is None or vad_queue is None:
            return
        try:
            snapshot = detector.observe(frame)
        except Exception as exc:
            self._set_failure(
                AudioEngineFailure("audio_vad_failed", str(exc) or type(exc).__name__)
            )
            return
        if snapshot.state in {
            VoiceActivityState.SPEECH_DETECTED,
            VoiceActivityState.SPEECH_ACTIVE,
            VoiceActivityState.END_OF_SPEECH,
        }:
            with self._state_lock:
                self._metrics.speech_seen = True
        if snapshot.state is previous:
            return
        with self._state_lock:
            self._last_vad_state = snapshot.state
        try:
            vad_queue.put(snapshot)
        except AudioQueueClosed:
            return

    def _observe_speech(self, frame: PcmFrame) -> None:
        try:
            peak = max(
                (abs(item[0]) for item in struct.iter_unpack("<h", frame.pcm16_le)), default=0
            )
        except (struct.error, ValueError):
            peak = 0
        if peak >= self._speech_peak_threshold:
            with self._state_lock:
                self._metrics.speech_seen = True

    def _set_failure(self, failure: AudioEngineFailure) -> None:
        with self._state_lock:
            if self._failure is None:
                self._failure = failure

    def _summary(
        self,
        generation: int,
        *,
        stop_latency_ms: int,
        stopped_within_budget: bool,
    ) -> AudioCaptureSummary:
        with self._state_lock:
            metrics = replace(self._metrics)
            started_at_ns = self._started_at_ns
            failure = self._failure
            input_name = self._capture.input_device_public_name
        return AudioCaptureSummary(
            generation=generation,
            captured_frames=metrics.captured_frames,
            encoded_frames=metrics.encoded_frames,
            uploaded_frames=metrics.uploaded_frames,
            dropped_pcm_frames=metrics.dropped_pcm_frames,
            uplink_overflow_count=metrics.uplink_overflow_count,
            speech_seen=metrics.speech_seen,
            stopped_within_budget=stopped_within_budget,
            stop_latency_ms=stop_latency_ms,
            input_device_public_name=input_name,
            first_pcm_latency_ms=_latency_ms(started_at_ns, metrics.first_pcm_at_ns),
            first_opus_latency_ms=_latency_ms(started_at_ns, metrics.first_opus_at_ns),
            first_opus_upload_latency_ms=_latency_ms(
                started_at_ns,
                metrics.first_opus_upload_at_ns,
            ),
            error_message=str(failure) if failure is not None else None,
        )


def _latency_ms(started_at_ns: int | None, completed_at_ns: int | None) -> int | None:
    if started_at_ns is None or completed_at_ns is None:
        return None
    return max(0, int((completed_at_ns - started_at_ns) / 1_000_000))
