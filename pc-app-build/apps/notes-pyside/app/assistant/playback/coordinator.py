"""Bridge wire-order downlink ingress to one real playback engine."""

# PLAYBACK_PACKET_IDLE_WATCHDOG_V1

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from ..events import AssistantEvent
from ..audio.gate6_contracts import PlaybackActivity
from ..protocol.events import DownlinkAudioFormat
from ..state import AssistantState
from .engine import AssistantPlaybackEngine
from .models import (
    EncodedDownlinkPacket,
    PlaybackCancelledSignal,
    PlaybackEndedSignal,
    PlaybackFailedSignal,
    PlaybackSignal,
    PlaybackStartedSignal,
    PlaybackSummary,
    TtsStreamContext,
)
from .opus_decoder import PyAvOpusDecoder
from .pyaudio_output import (
    PyAudioOutputAdapter,
    PyAudioOutputPlan,
    probe_default_output_plan,
)
from .ports import RenderReferenceCallback
from .runtime_events import (
    ActualPlaybackEnded,
    ActualPlaybackStarted,
    PlaybackProgressUpdated,
    RuntimePlaybackCancelled,
    RuntimePlaybackFailed,
)

RuntimeEventSink = Callable[[AssistantEvent], Awaitable[None]]
OutputPlanProvider = Callable[[], PyAudioOutputPlan]
RuntimeStateProvider = Callable[[], AssistantState]
PlaybackActivitySink = Callable[[PlaybackActivity], None]


class PlaybackCoordinator:
    """Own exactly one current playback generation outside the Runtime event queue."""

    def __init__(
        self,
        *,
        clock_ns: Callable[[], int],
        output_plan_provider: OutputPlanProvider = probe_default_output_plan,
        stream_start_timeout_seconds: float = 6.0,
        decoder_progress_timeout_seconds: float = 6.0,
        packet_idle_timeout_seconds: float = 8.0,
        playback_activity_sink: PlaybackActivitySink | None = None,
        render_reference_sink: RenderReferenceCallback | None = None,
        engine_factory: (
            Callable[
                [
                    TtsStreamContext,
                    PyAudioOutputPlan,
                    Callable[[PlaybackSignal], Awaitable[None]],
                ],
                AssistantPlaybackEngine,
            ]
            | None
        ) = None,
    ) -> None:
        if (
            stream_start_timeout_seconds <= 0
            or decoder_progress_timeout_seconds <= 0
            or packet_idle_timeout_seconds <= 0
        ):
            raise ValueError("playback watchdog timeouts must be positive")
        self._clock_ns = clock_ns
        self._output_plan_provider = output_plan_provider
        self._stream_start_timeout_seconds = stream_start_timeout_seconds
        self._decoder_progress_timeout_seconds = decoder_progress_timeout_seconds
        self._packet_idle_timeout_seconds = packet_idle_timeout_seconds
        self._engine_factory = engine_factory or self._make_real_engine
        self._playback_activity_sink = playback_activity_sink
        self._render_reference_sink = render_reference_sink
        self._event_sink: RuntimeEventSink | None = None
        self._runtime_state_provider: RuntimeStateProvider | None = None
        self._bound_generation: int | None = None
        self._engine: AssistantPlaybackEngine | None = None
        self._context: TtsStreamContext | None = None
        self._output_plan: PyAudioOutputPlan | None = None
        self._packet_sequence = 0
        self._last_packet_received_at_ns: int | None = None
        self._last_summary: PlaybackSummary | None = None
        self._last_latency_sample: dict[str, float | None] = {}
        self._watchdog_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        self._invalidated_turns: dict[tuple[int, int], None] = {}

    def bind_runtime_state_provider(self, provider: RuntimeStateProvider) -> None:
        self._runtime_state_provider = provider

    def bind_render_reference_sink(
        self,
        sink: RenderReferenceCallback | None,
    ) -> None:
        self._render_reference_sink = sink

    def streaming_generation_for_turn(self, turn_token: int) -> int | None:
        provider = self._runtime_state_provider
        if provider is None:
            return None
        state = provider()
        conversation = state.conversation
        if (
            conversation.streaming_session_active
            and conversation.active_streaming_turn_token == turn_token
            and conversation.streaming_generation > 0
        ):
            return conversation.streaming_generation
        return None

    @property
    def active_context(self) -> TtsStreamContext | None:
        return self._context

    @property
    def last_summary(self) -> PlaybackSummary | None:
        return self._last_summary

    @property
    def last_latency_sample(self) -> dict[str, float | None]:
        return dict(self._last_latency_sample)

    @property
    def output_plan(self) -> PyAudioOutputPlan | None:
        return self._output_plan

    @property
    def task_running(self) -> bool:
        return bool(self._engine and self._engine.task_running)

    @property
    def output_running(self) -> bool:
        return bool(self._engine and self._engine.output_running)

    @property
    def encoded_packet_count(self) -> int:
        return self._engine.encoded_packet_count if self._engine else 0

    @property
    def pcm_buffered_bytes(self) -> int:
        return self._engine.pcm_buffered_bytes if self._engine else 0

    async def open_generation(self, generation: int, event_sink: RuntimeEventSink) -> None:
        if generation <= 0:
            raise ValueError("connection generation must be positive")
        async with self._lock:
            if self._bound_generation not in {None, generation}:
                await self._cancel_locked("connection_generation_replaced")
            self._bound_generation = generation
            self._event_sink = event_sink

    async def begin_stream(
        self,
        *,
        connection_generation: int,
        stream_sequence: int,
        turn_token: int,
        streaming_generation: int | None,
        wire_format: DownlinkAudioFormat,
        session_id: str | None,
        started_at_ns: int,
    ) -> TtsStreamContext | None:
        if wire_format.codec != "opus":
            await self._emit_begin_failure(
                connection_generation,
                stream_sequence,
                turn_token,
                "unsupported_downlink_codec",
                f"unsupported downlink codec: {wire_format.codec}",
            )
            return None
        if (connection_generation, turn_token) in self._invalidated_turns:
            return None
        async with self._lock:
            if connection_generation != self._bound_generation:
                return None
            await self._cancel_locked("new_tts_stream")
            playback_generation = stream_sequence
            context = TtsStreamContext(
                connection_generation=connection_generation,
                stream_sequence=stream_sequence,
                playback_generation=playback_generation,
                turn_token=turn_token,
                streaming_generation=streaming_generation,
                wire_format=wire_format,
                started_at_ns=started_at_ns,
                session_id=session_id,
            )
            try:
                plan = await asyncio.to_thread(self._output_plan_provider)
                engine = self._engine_factory(context, plan, self._on_playback_signal)
                await engine.arm(context)
            except Exception as exc:
                await self._emit_begin_failure(
                    connection_generation,
                    stream_sequence,
                    turn_token,
                    "output_device_unavailable",
                    f"{type(exc).__name__}: {str(exc)[:180]}",
                )
                return None
            self._context = context
            self._engine = engine
            self._output_plan = plan
            self._packet_sequence = 0
            self._last_packet_received_at_ns = None
            self._watchdog_task = asyncio.create_task(
                self._watch_playback_progress(context, engine),
                name=f"assistant-playback-watchdog-{playback_generation}",
            )
            self._set_playback_activity(PlaybackActivity.BUFFERING)
            return context

    def offer_payload_nowait(
        self,
        *,
        connection_generation: int,
        stream_sequence: int,
        payload: bytes,
        received_at_ns: int,
    ) -> bool:
        context = self._context
        engine = self._engine
        if (
            context is None
            or engine is None
            or connection_generation != context.connection_generation
            or stream_sequence != context.stream_sequence
            or not payload
        ):
            return False
        self._packet_sequence += 1
        accepted = engine.offer_packet(
            EncodedDownlinkPacket(
                connection_generation=connection_generation,
                stream_sequence=stream_sequence,
                packet_sequence=self._packet_sequence,
                received_at_ns=received_at_ns,
                payload=payload,
            )
        )
        if accepted:
            self._last_packet_received_at_ns = received_at_ns
        return accepted

    async def start_playback(
        self,
        *,
        connection_generation: int,
        stream_sequence: int,
        playback_generation: int,
    ) -> bool:
        async with self._lock:
            context = self._context
            engine = self._engine
            if (
                context is None
                or engine is None
                or context.connection_generation != connection_generation
                or context.stream_sequence != stream_sequence
                or context.playback_generation != playback_generation
            ):
                return False
            try:
                await engine.start(playback_generation)
            except Exception as exc:
                await engine.fail(
                    code="playback_output_start_failed",
                    message=f"{type(exc).__name__}: {str(exc)[:180]}",
                )
                return False
            return True

    def end_stream_nowait(
        self,
        *,
        connection_generation: int,
        stream_sequence: int,
        reason: str,
        at_ns: int,
    ) -> bool:
        context = self._context
        engine = self._engine
        if (
            context is None
            or engine is None
            or context.connection_generation != connection_generation
            or context.stream_sequence != stream_sequence
        ):
            return False
        accepted = engine.end_stream(stream_sequence, reason=reason, at_ns=at_ns)
        if accepted:
            self._set_playback_activity(PlaybackActivity.DRAINING)
        return accepted

    async def cancel(self, reason: str, playback_generation: int | None = None) -> bool:
        async with self._lock:
            context = self._context
            if context is None:
                return False
            if (
                playback_generation is not None
                and context.playback_generation != playback_generation
            ):
                return False
            await self._cancel_locked(reason)
            return True

    async def close_generation(self, generation: int, reason: str) -> None:
        async with self._lock:
            if self._bound_generation != generation:
                return
            await self._cancel_locked(reason)
            self._bound_generation = None
            self._event_sink = None

    async def close(self) -> None:
        async with self._lock:
            await self._cancel_locked("playback_coordinator_close")
            self._bound_generation = None
            self._event_sink = None

    async def _cancel_locked(self, reason: str) -> None:
        await self._cancel_watchdog()
        engine = self._engine
        context = self._context
        if context is not None and reason.startswith("acoustic_barge_in"):
            self._invalidated_turns[(context.connection_generation, context.turn_token)] = None
            if len(self._invalidated_turns) > 256:
                self._invalidated_turns.pop(next(iter(self._invalidated_turns)))
        self._engine = None
        self._context = None
        self._output_plan = None
        self._packet_sequence = 0
        self._last_packet_received_at_ns = None
        if engine is None:
            self._set_playback_activity(PlaybackActivity.INACTIVE)
            return
        self._set_playback_activity(PlaybackActivity.CANCELLING)
        try:
            await engine.cancel(reason)
        finally:
            await engine.close()
            self._set_playback_activity(PlaybackActivity.INACTIVE)

    async def _on_playback_signal(self, signal: PlaybackSignal) -> None:
        sink = self._event_sink
        if sink is None:
            return
        if isinstance(signal, PlaybackStartedSignal):
            self._set_playback_activity(PlaybackActivity.PLAYING)
            plan = self._output_plan
            await sink(
                ActualPlaybackStarted(
                    at_ns=signal.at_ns,
                    connection_generation=signal.connection_generation,
                    stream_sequence=signal.stream_sequence,
                    playback_generation=signal.playback_generation,
                    turn_token=signal.turn_token,
                    streaming_generation=signal.streaming_generation,
                    output_device_public_name=(plan.device_public_name if plan else None),
                )
            )
            await self._emit_progress()
            return
        if isinstance(signal, PlaybackEndedSignal):
            self._set_playback_activity(PlaybackActivity.INACTIVE)
            await self._cancel_watchdog()
            self._last_summary = signal.summary
            metrics = self._engine.metrics if self._engine is not None else None
            self._last_latency_sample = self._latency_sample(metrics)
            await self._emit_progress(summary=signal.summary)
            await sink(
                ActualPlaybackEnded(
                    at_ns=self._clock_ns(),
                    summary=signal.summary,
                )
            )
            return
        if isinstance(signal, PlaybackCancelledSignal):
            self._set_playback_activity(PlaybackActivity.INACTIVE)
            await self._cancel_watchdog()
            await sink(
                RuntimePlaybackCancelled(
                    at_ns=signal.at_ns,
                    connection_generation=signal.connection_generation,
                    stream_sequence=signal.stream_sequence,
                    playback_generation=signal.playback_generation,
                    turn_token=signal.turn_token,
                    reason=signal.reason,
                )
            )
            return
        if isinstance(signal, PlaybackFailedSignal):
            self._set_playback_activity(PlaybackActivity.INACTIVE)
            await self._cancel_watchdog()
            await sink(
                RuntimePlaybackFailed(
                    at_ns=signal.at_ns,
                    connection_generation=signal.connection_generation,
                    stream_sequence=signal.stream_sequence,
                    playback_generation=signal.playback_generation,
                    turn_token=signal.turn_token,
                    code=signal.code,
                    message=signal.message,
                )
            )

    def _set_playback_activity(self, activity: PlaybackActivity) -> None:
        sink = self._playback_activity_sink
        if sink is None:
            return
        try:
            sink(activity)
        except Exception:
            return

    async def _watch_playback_progress(
        self,
        context: TtsStreamContext,
        engine: AssistantPlaybackEngine,
    ) -> None:
        try:
            while self._context is context and self._engine is engine:
                await asyncio.sleep(0.1)
                metrics = engine.metrics
                now_ns = self._clock_ns()
                if metrics.first_packet_at_ns is None:
                    if (
                        now_ns - context.started_at_ns
                        >= self._stream_start_timeout_seconds * 1_000_000_000
                    ):
                        await engine.fail(
                            code="playback_stream_start_timeout",
                            message="TTS stream produced no binary packet before watchdog timeout",
                        )
                        return
                    continue
                if (
                    metrics.first_decoded_at_ns is None
                    and now_ns - metrics.first_packet_at_ns
                    >= self._decoder_progress_timeout_seconds * 1_000_000_000
                ):
                    await engine.fail(
                        code="playback_decoder_progress_timeout",
                        message="Opus decoder produced no PCM before watchdog timeout",
                    )
                    return
                last_packet_at_ns = self._last_packet_received_at_ns
                if (
                    metrics.first_decoded_at_ns is not None
                    and metrics.input_terminal_at_ns is None
                    and last_packet_at_ns is not None
                    and engine.pcm_buffered_bytes == 0
                    and now_ns - last_packet_at_ns
                    >= self._packet_idle_timeout_seconds * 1_000_000_000
                ):
                    await engine.fail(
                        code="playback_packet_idle_timeout",
                        message=(
                            "TTS playback received no binary audio while the "
                            "input stream remained non-terminal"
                        ),
                    )
                    return
                if metrics.playback_started_at_ns is not None:
                    await self._emit_progress()
        except asyncio.CancelledError:
            raise

    async def _cancel_watchdog(self) -> None:
        task = self._watchdog_task
        self._watchdog_task = None
        if task is None or task.done() or task is asyncio.current_task():
            return
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def _emit_progress(self, summary: PlaybackSummary | None = None) -> None:
        sink = self._event_sink
        context = self._context
        engine = self._engine
        if sink is None or context is None:
            return
        metrics = engine.metrics if engine is not None else None
        await sink(
            PlaybackProgressUpdated(
                at_ns=self._clock_ns(),
                connection_generation=context.connection_generation,
                stream_sequence=context.stream_sequence,
                playback_generation=context.playback_generation,
                turn_token=context.turn_token,
                decoded_sample_frames=(
                    summary.decoded_sample_frames
                    if summary is not None
                    else (metrics.decoded_sample_frames if metrics else 0)
                ),
                played_sample_frames=(
                    summary.played_sample_frames
                    if summary is not None
                    else (metrics.played_sample_frames if metrics else 0)
                ),
                encoded_packets_received=(
                    summary.encoded_packets_received
                    if summary is not None
                    else (metrics.encoded_packets_received if metrics else 0)
                ),
                pcm_underflow_count=(
                    summary.pcm_underflow_count
                    if summary is not None
                    else (metrics.pcm_underflow_count if metrics else 0)
                ),
                encoded_overflow_count=(
                    summary.encoded_overflow_count
                    if summary is not None
                    else (metrics.encoded_overflow_count if metrics else 0)
                ),
                pcm_overflow_count=(
                    summary.pcm_overflow_count
                    if summary is not None
                    else (metrics.pcm_overflow_count if metrics else 0)
                ),
            )
        )

    async def _emit_begin_failure(
        self,
        connection_generation: int,
        stream_sequence: int,
        turn_token: int,
        code: str,
        message: str,
    ) -> None:
        sink = self._event_sink
        if sink is None:
            return
        await sink(
            RuntimePlaybackFailed(
                at_ns=self._clock_ns(),
                connection_generation=connection_generation,
                stream_sequence=stream_sequence,
                playback_generation=stream_sequence,
                turn_token=turn_token,
                code=code,
                message=message,
            )
        )

    @staticmethod
    def _latency_sample(metrics) -> dict[str, float | None]:
        def delta(start: int | None, end: int | None) -> float | None:
            if start is None or end is None or end < start:
                return None
            return round((end - start) / 1_000_000, 3)

        if metrics is None:
            return {}
        return {
            "first_packet_to_decode_ms": delta(
                metrics.first_packet_at_ns, metrics.first_decoded_at_ns
            ),
            "first_packet_to_playback_start_ms": delta(
                metrics.first_packet_at_ns, metrics.playback_started_at_ns
            ),
            "terminal_to_physical_drain_ms": delta(
                metrics.input_terminal_at_ns, metrics.playback_ended_at_ns
            ),
        }

    def _make_real_engine(
        self,
        context: TtsStreamContext,
        plan: PyAudioOutputPlan,
        event_sink: Callable[[PlaybackSignal], Awaitable[None]],
    ) -> AssistantPlaybackEngine:
        return AssistantPlaybackEngine(
            decoder_factory=lambda _context: PyAvOpusDecoder(
                plan.pcm_format,
                clock_ns=self._clock_ns,
            ),
            output_factory=lambda: PyAudioOutputAdapter(
                plan,
                render_reference_callback=self._render_reference_sink,
                clock_ns=self._clock_ns,
            ),
            event_sink=event_sink,
            clock_ns=self._clock_ns,
            encoded_budget_ms=2_000,
            pcm_budget_ms=2_000,
            startup_prebuffer_chunks=2,
            drain_timeout_seconds=8.0,
        )
