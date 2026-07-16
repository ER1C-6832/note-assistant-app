"""Single-worker bounded playback engine with physical-drain semantics."""

from __future__ import annotations

import asyncio
import math
from collections.abc import Callable

from .ingress import DownlinkAudioIngress, IngressOfferStatus
from .models import (
    DecodedPcmChunk,
    EncodedDownlinkPacket,
    PlaybackCancelledSignal,
    PlaybackEndedSignal,
    PlaybackFailedSignal,
    PlaybackLifecycleState,
    PlaybackMetrics,
    PlaybackSignal,
    PlaybackStartedSignal,
    PlaybackSummary,
    TtsStreamContext,
)
from .ports import AudioOutputPort, OpusDecoderPort, PlaybackEventSink
from .queues import BoundedEncodedDownlinkQueue, PcmPlaybackBuffer


class _PcmOverflowError(RuntimeError):
    pass


class AssistantPlaybackEngine:
    """Own one decoder worker and one output lifecycle for the current stream."""

    def __init__(
        self,
        *,
        decoder_factory: Callable[[TtsStreamContext], OpusDecoderPort],
        output_factory: Callable[[], AudioOutputPort],
        event_sink: PlaybackEventSink,
        clock_ns: Callable[[], int],
        encoded_budget_ms: int = 2_000,
        pcm_budget_ms: int = 2_000,
        startup_prebuffer_chunks: int = 2,
    ) -> None:
        if encoded_budget_ms <= 0 or pcm_budget_ms <= 0:
            raise ValueError("playback budgets must be positive")
        if startup_prebuffer_chunks <= 0:
            raise ValueError("startup_prebuffer_chunks must be positive")
        self._decoder_factory = decoder_factory
        self._output_factory = output_factory
        self._event_sink = event_sink
        self._clock_ns = clock_ns
        self._encoded_budget_ms = encoded_budget_ms
        self._pcm_budget_ms = pcm_budget_ms
        self._startup_prebuffer_chunks = startup_prebuffer_chunks

        self._context: TtsStreamContext | None = None
        self._decoder: OpusDecoderPort | None = None
        self._output: AudioOutputPort | None = None
        self._ingress: DownlinkAudioIngress | None = None
        self._encoded: BoundedEncodedDownlinkQueue | None = None
        self._pcm: PcmPlaybackBuffer | None = None
        self._worker: asyncio.Task[None] | None = None
        self._done: asyncio.Future[PlaybackSignal] | None = None
        self._drained: asyncio.Future[None] | None = None
        self._started_emit_task: asyncio.Task[None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._metrics = PlaybackMetrics()
        self._lifecycle: PlaybackLifecycleState | None = None
        self._last_packet_sequence = 0
        self._decoded_chunks_buffered = 0
        self._output_started = False
        self._started_signal_emitted = False
        self._terminal_reason = "tts_terminal"
        self._failed = False
        self._cancelled = False
        self._closed = False

    @property
    def lifecycle(self) -> PlaybackLifecycleState | None:
        return self._lifecycle

    @property
    def task_running(self) -> bool:
        return self._worker is not None and not self._worker.done()

    @property
    def output_running(self) -> bool:
        return bool(self._output and self._output.running)

    @property
    def encoded_packet_count(self) -> int:
        return self._encoded.packet_count if self._encoded else 0

    @property
    def pcm_buffered_bytes(self) -> int:
        return self._pcm.buffered_bytes if self._pcm else 0

    @property
    def metrics(self) -> PlaybackMetrics:
        return self._metrics

    async def arm(self, context: TtsStreamContext) -> None:
        if self._closed:
            raise RuntimeError("playback engine is closed")
        if self._lifecycle in {
            PlaybackLifecycleState.ARMED,
            PlaybackLifecycleState.BUFFERING,
            PlaybackLifecycleState.PLAYING,
        }:
            raise RuntimeError("playback stream already active")

        self._loop = asyncio.get_running_loop()
        self._context = context
        self._decoder = self._decoder_factory(context)
        self._output = self._output_factory()
        packet_capacity = max(
            1,
            math.ceil(self._encoded_budget_ms / context.wire_format.frame_duration_ms),
        )
        self._ingress = DownlinkAudioIngress(context, packet_capacity=packet_capacity)
        self._encoded = self._ingress.queue
        pcm_format = self._decoder.pcm_format
        pcm_capacity_bytes = (
            pcm_format.sample_rate_hz * pcm_format.frame_size_bytes * self._pcm_budget_ms // 1_000
        )
        pcm_capacity_bytes -= pcm_capacity_bytes % pcm_format.frame_size_bytes
        self._pcm = PcmPlaybackBuffer(pcm_format, pcm_capacity_bytes)
        self._done = self._loop.create_future()
        self._drained = self._loop.create_future()
        self._worker = None
        self._started_emit_task = None
        self._metrics = PlaybackMetrics()
        self._lifecycle = PlaybackLifecycleState.ARMED
        self._last_packet_sequence = 0
        self._decoded_chunks_buffered = 0
        self._output_started = False
        self._started_signal_emitted = False
        self._terminal_reason = "tts_terminal"
        self._failed = False
        self._cancelled = False

    def offer_packet(self, packet: EncodedDownlinkPacket) -> bool:
        self._require_context()
        ingress = self._require_ingress()
        if self._terminal_state():
            self._metrics.stale_packet_count += 1
            return False
        status = ingress.offer(packet)
        if status in {IngressOfferStatus.STALE, IngressOfferStatus.TERMINAL}:
            self._metrics.stale_packet_count += 1
            return False
        if status is IngressOfferStatus.OVERFLOW:
            self._metrics.encoded_overflow_count += 1
            self._schedule_failure(
                code="downlink_overflow",
                message="bounded encoded downlink queue overflow",
            )
            return False
        self._last_packet_sequence = packet.packet_sequence
        self._metrics.encoded_packets_received += 1
        self._metrics.encoded_bytes_received += len(packet.payload)
        if self._metrics.first_packet_at_ns is None:
            self._metrics.first_packet_at_ns = packet.received_at_ns
        return True

    def end_stream(self, stream_sequence: int, *, reason: str, at_ns: int) -> bool:
        context = self._require_context()
        ingress = self._require_ingress()
        if self._terminal_state():
            return False
        if not ingress.end(
            connection_generation=context.connection_generation,
            stream_sequence=stream_sequence,
            reason=reason,
            at_ns=at_ns,
        ):
            return False
        self._terminal_reason = reason
        self._metrics.input_terminal_at_ns = at_ns
        return True

    async def start(self, playback_generation: int) -> None:
        context = self._require_context()
        if playback_generation != context.playback_generation:
            raise ValueError("stale playback_generation")
        if self._worker is not None:
            return
        if self._terminal_state():
            return
        assert self._output is not None
        assert self._pcm is not None
        assert self._drained is not None
        await self._output.open(
            context,
            self._pcm,
            self._on_samples_consumed,
            self._on_output_drained,
        )
        self._lifecycle = PlaybackLifecycleState.BUFFERING
        self._worker = asyncio.create_task(
            self._worker_loop(),
            name=f"assistant-playback-worker-{context.playback_generation}",
        )

    async def wait_finished(self, timeout_seconds: float = 5.0) -> PlaybackSignal:
        if self._done is None:
            raise RuntimeError("playback stream is not armed")
        return await asyncio.wait_for(asyncio.shield(self._done), timeout=timeout_seconds)

    async def cancel(self, reason: str) -> PlaybackCancelledSignal | None:
        if self._context is None or self._terminal_state():
            return None
        self._cancelled = True
        self._lifecycle = PlaybackLifecycleState.CANCELLED
        context = self._context
        if self._ingress is not None:
            self._ingress.abort()
        if self._pcm is not None:
            self._pcm.cancel()
        await self._stop_components(cancel_worker=True)
        signal = PlaybackCancelledSignal(
            connection_generation=context.connection_generation,
            stream_sequence=context.stream_sequence,
            playback_generation=context.playback_generation,
            turn_token=context.turn_token,
            reason=reason,
            at_ns=self._clock_ns(),
        )
        await self._event_sink(signal)
        self._set_done(signal)
        return signal

    async def close(self) -> None:
        if self._closed:
            return
        if self._context is not None and not self._terminal_state():
            await self.cancel("playback_engine_close")
        else:
            await self._stop_components(cancel_worker=True)
        self._lifecycle = PlaybackLifecycleState.CLOSED
        self._closed = True

    async def _worker_loop(self) -> None:
        encoded = self._require_encoded()
        decoder = self._require_decoder()
        pcm = self._require_pcm()
        try:
            while True:
                item = await encoded.get()
                try:
                    if isinstance(item, EncodedDownlinkPacket):
                        chunks = decoder.decode(item)
                        self._accept_decoded(chunks)
                        await self._maybe_start_output(force=False)
                        continue

                    chunks = decoder.flush()
                    self._accept_decoded(chunks)
                    pcm.mark_terminal()
                    await self._maybe_start_output(force=True)
                    if self._metrics.decoded_sample_frames == 0:
                        await self._fail(
                            code="playback_no_audio",
                            message="TTS stream ended without playable PCM",
                            cancel_worker=False,
                        )
                        return
                    assert self._drained is not None
                    await self._drained
                    if self._cancelled or self._failed:
                        return
                    if not pcm.terminal_and_empty:
                        await self._fail(
                            code="playback_drain_incomplete",
                            message="output reported drain before PCM buffer was empty",
                            cancel_worker=False,
                        )
                        return
                    if self._started_emit_task is not None:
                        await self._started_emit_task
                    self._metrics.pcm_underflow_count = pcm.underflow_count
                    self._metrics.buffer_peak_bytes = pcm.peak_bytes
                    self._metrics.playback_ended_at_ns = self._clock_ns()
                    await self._stop_components(cancel_worker=False)
                    summary = self._build_summary(natural_end=True)
                    signal = PlaybackEndedSignal(summary=summary)
                    await self._event_sink(signal)
                    self._lifecycle = PlaybackLifecycleState.DRAINED
                    self._set_done(signal)
                    return
                finally:
                    encoded.task_done(item)
        except asyncio.CancelledError:
            raise
        except _PcmOverflowError as exc:
            await self._fail(
                code="pcm_overflow",
                message=str(exc),
                cancel_worker=False,
            )
        except Exception as exc:
            await self._fail(
                code="playback_worker_failed",
                message=f"{type(exc).__name__}: {str(exc)[:160]}",
                cancel_worker=False,
            )

    def _accept_decoded(self, chunks: tuple[DecodedPcmChunk, ...]) -> None:
        pcm = self._require_pcm()
        for chunk in chunks:
            if chunk.pcm_format != pcm.pcm_format:
                raise ValueError("decoder changed PCM format within a stream")
            if not pcm.offer(chunk.payload):
                self._metrics.pcm_overflow_count += 1
                raise _PcmOverflowError("bounded PCM playback buffer overflow")
            self._decoded_chunks_buffered += 1
            self._metrics.decoded_chunks += 1
            self._metrics.decoded_sample_frames += chunk.sample_frames
            if self._metrics.first_decoded_at_ns is None:
                self._metrics.first_decoded_at_ns = chunk.decoded_at_ns
            self._metrics.buffer_peak_bytes = max(
                self._metrics.buffer_peak_bytes,
                pcm.buffered_bytes,
            )

    async def _maybe_start_output(self, *, force: bool) -> None:
        if self._output_started or self._output is None:
            return
        if not force and self._decoded_chunks_buffered < self._startup_prebuffer_chunks:
            return
        if self._metrics.decoded_sample_frames <= 0:
            return
        await self._output.start()
        self._output_started = True

    def _on_samples_consumed(self, byte_count: int, sample_frames: int) -> None:
        del byte_count
        loop = self._loop
        if loop is None:
            return
        loop.call_soon_threadsafe(self._record_samples_consumed, sample_frames)

    def _record_samples_consumed(self, sample_frames: int) -> None:
        if self._terminal_state() or sample_frames <= 0:
            return
        self._metrics.played_sample_frames += sample_frames
        if not self._started_signal_emitted:
            self._started_signal_emitted = True
            self._lifecycle = PlaybackLifecycleState.PLAYING
            self._metrics.playback_started_at_ns = self._clock_ns()
            context = self._require_context()
            signal = PlaybackStartedSignal(
                connection_generation=context.connection_generation,
                stream_sequence=context.stream_sequence,
                playback_generation=context.playback_generation,
                turn_token=context.turn_token,
                streaming_generation=context.streaming_generation,
                at_ns=self._metrics.playback_started_at_ns,
            )
            self._started_emit_task = asyncio.create_task(
                self._event_sink(signal),
                name=f"assistant-playback-started-{context.playback_generation}",
            )

    def _on_output_drained(self) -> None:
        loop = self._loop
        if loop is None:
            return
        loop.call_soon_threadsafe(self._mark_output_drained)

    def _mark_output_drained(self) -> None:
        if self._drained is not None and not self._drained.done():
            self._drained.set_result(None)

    def _schedule_failure(self, *, code: str, message: str) -> None:
        loop = self._loop
        if loop is None or self._failed or self._cancelled:
            return
        loop.create_task(
            self._fail(code=code, message=message, cancel_worker=True),
            name=f"assistant-playback-failure-{code}",
        )

    async def _fail(
        self,
        *,
        code: str,
        message: str,
        cancel_worker: bool,
    ) -> PlaybackFailedSignal | None:
        if self._context is None or self._failed or self._cancelled:
            return None
        self._failed = True
        self._lifecycle = PlaybackLifecycleState.FAILED
        context = self._context
        if self._ingress is not None:
            self._ingress.abort()
        if self._pcm is not None:
            self._pcm.cancel()
        await self._stop_components(cancel_worker=cancel_worker)
        signal = PlaybackFailedSignal(
            connection_generation=context.connection_generation,
            stream_sequence=context.stream_sequence,
            playback_generation=context.playback_generation,
            turn_token=context.turn_token,
            code=code,
            message=message,
            at_ns=self._clock_ns(),
        )
        await self._event_sink(signal)
        self._set_done(signal)
        return signal

    async def _stop_components(self, *, cancel_worker: bool) -> None:
        current = asyncio.current_task()
        worker = self._worker
        if cancel_worker and worker is not None and worker is not current and not worker.done():
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
        if self._output is not None:
            try:
                await self._output.stop()
            finally:
                await self._output.close()
        if self._decoder is not None:
            self._decoder.close()
        if worker is not current:
            self._worker = None

    def _build_summary(self, *, natural_end: bool) -> PlaybackSummary:
        context = self._require_context()
        output = self._output
        return PlaybackSummary(
            connection_generation=context.connection_generation,
            stream_sequence=context.stream_sequence,
            playback_generation=context.playback_generation,
            turn_token=context.turn_token,
            streaming_generation=context.streaming_generation,
            reason=self._terminal_reason,
            natural_end=natural_end,
            encoded_packets_received=self._metrics.encoded_packets_received,
            encoded_bytes_received=self._metrics.encoded_bytes_received,
            decoded_chunks=self._metrics.decoded_chunks,
            decoded_sample_frames=self._metrics.decoded_sample_frames,
            played_sample_frames=self._metrics.played_sample_frames,
            encoded_overflow_count=self._metrics.encoded_overflow_count,
            pcm_overflow_count=self._metrics.pcm_overflow_count,
            pcm_underflow_count=self._metrics.pcm_underflow_count,
            buffer_peak_bytes=self._metrics.buffer_peak_bytes,
            output_device_public_name=(output.device_public_name if output else None),
        )

    def _terminal_state(self) -> bool:
        return (
            self._failed
            or self._cancelled
            or self._lifecycle
            in {
                PlaybackLifecycleState.DRAINED,
                PlaybackLifecycleState.CLOSED,
            }
        )

    def _set_done(self, signal: PlaybackSignal) -> None:
        if self._done is not None and not self._done.done():
            self._done.set_result(signal)

    def _require_context(self) -> TtsStreamContext:
        if self._context is None:
            raise RuntimeError("playback stream is not armed")
        return self._context

    def _require_decoder(self) -> OpusDecoderPort:
        if self._decoder is None:
            raise RuntimeError("decoder is not initialized")
        return self._decoder

    def _require_ingress(self) -> DownlinkAudioIngress:
        if self._ingress is None:
            raise RuntimeError("downlink ingress is not initialized")
        return self._ingress

    def _require_encoded(self) -> BoundedEncodedDownlinkQueue:
        if self._encoded is None:
            raise RuntimeError("encoded queue is not initialized")
        return self._encoded

    def _require_pcm(self) -> PcmPlaybackBuffer:
        if self._pcm is None:
            raise RuntimeError("PCM buffer is not initialized")
        return self._pcm
