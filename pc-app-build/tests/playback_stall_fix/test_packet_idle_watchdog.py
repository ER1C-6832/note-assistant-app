from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from app.assistant.playback import PcmAudioFormat, PlaybackCoordinator, PyAudioOutputPlan
from app.assistant.playback.models import PlaybackFailedSignal
from app.assistant.playback.runtime_events import RuntimePlaybackFailed
from app.assistant.protocol import DownlinkAudioFormat


@dataclass
class _Metrics:
    first_packet_at_ns: int | None = None
    first_decoded_at_ns: int | None = None
    playback_started_at_ns: int | None = None
    input_terminal_at_ns: int | None = None
    playback_ended_at_ns: int | None = None
    decoded_sample_frames: int = 960
    played_sample_frames: int = 960
    encoded_packets_received: int = 1
    pcm_underflow_count: int = 0
    encoded_overflow_count: int = 0
    pcm_overflow_count: int = 0


class _StallingEngine:
    def __init__(self, context, sink) -> None:
        self._context = context
        self._sink = sink
        self.metrics = _Metrics()
        self.task_running = False
        self.output_running = False
        self.pcm_buffered_bytes = 0
        self.failed_codes: list[str] = []

    async def arm(self, context) -> None:
        assert context is self._context

    async def start(self, playback_generation: int) -> None:
        assert playback_generation == self._context.playback_generation
        self.task_running = True
        self.output_running = True

    def offer_packet(self, packet) -> bool:
        self.metrics.first_packet_at_ns = packet.received_at_ns
        self.metrics.first_decoded_at_ns = packet.received_at_ns
        return True

    def end_stream(self, stream_sequence: int, *, reason: str, at_ns: int) -> bool:
        del stream_sequence, reason
        self.metrics.input_terminal_at_ns = at_ns
        return True

    async def fail(self, *, code: str, message: str):
        self.failed_codes.append(code)
        self.task_running = False
        self.output_running = False
        signal = PlaybackFailedSignal(
            connection_generation=self._context.connection_generation,
            stream_sequence=self._context.stream_sequence,
            playback_generation=self._context.playback_generation,
            turn_token=self._context.turn_token,
            code=code,
            message=message,
            at_ns=self.metrics.first_decoded_at_ns or 0,
        )
        await self._sink(signal)
        return signal

    async def cancel(self, reason: str):
        del reason
        self.task_running = False
        self.output_running = False
        return None

    async def close(self) -> None:
        self.task_running = False
        self.output_running = False


@pytest.mark.asyncio
async def test_non_terminal_packet_idle_fails_and_stops_output() -> None:
    now_ns = 0

    def clock_ns() -> int:
        return now_ns

    plan = PyAudioOutputPlan(0, "Fake", PcmAudioFormat(48_000, 2), 960)
    engines: list[_StallingEngine] = []

    def engine_factory(context, selected, sink):
        assert selected == plan
        engine = _StallingEngine(context, sink)
        engines.append(engine)
        return engine

    events = []

    async def sink(event) -> None:
        events.append(event)

    coordinator = PlaybackCoordinator(
        clock_ns=clock_ns,
        output_plan_provider=lambda: plan,
        engine_factory=engine_factory,
        stream_start_timeout_seconds=1.0,
        decoder_progress_timeout_seconds=1.0,
        packet_idle_timeout_seconds=0.01,
    )
    await coordinator.open_generation(4, sink)
    context = await coordinator.begin_stream(
        connection_generation=4,
        stream_sequence=1,
        turn_token=2,
        streaming_generation=None,
        wire_format=DownlinkAudioFormat("opus", 24_000, 1, 20.0),
        session_id="session",
        started_at_ns=0,
    )
    assert context is not None
    assert coordinator.offer_payload_nowait(
        connection_generation=4,
        stream_sequence=1,
        payload=b"opus",
        received_at_ns=1_000_000,
    )
    assert await coordinator.start_playback(
        connection_generation=4,
        stream_sequence=1,
        playback_generation=1,
    )

    now_ns = 20_000_000
    for _ in range(20):
        if any(isinstance(event, RuntimePlaybackFailed) for event in events):
            break
        await asyncio.sleep(0.02)

    failure = next(event for event in events if isinstance(event, RuntimePlaybackFailed))
    assert failure.code == "playback_packet_idle_timeout"
    assert engines[0].failed_codes == ["playback_packet_idle_timeout"]
    assert not engines[0].task_running
    assert not engines[0].output_running
    await coordinator.close_generation(4, "test_complete")


@pytest.mark.asyncio
async def test_terminal_input_never_triggers_packet_idle_failure() -> None:
    now_ns = 0

    def clock_ns() -> int:
        return now_ns

    plan = PyAudioOutputPlan(0, "Fake", PcmAudioFormat(48_000, 2), 960)

    def engine_factory(context, selected, sink):
        assert selected == plan
        return _StallingEngine(context, sink)

    events = []

    async def sink(event) -> None:
        events.append(event)

    coordinator = PlaybackCoordinator(
        clock_ns=clock_ns,
        output_plan_provider=lambda: plan,
        engine_factory=engine_factory,
        packet_idle_timeout_seconds=0.01,
    )
    await coordinator.open_generation(5, sink)
    context = await coordinator.begin_stream(
        connection_generation=5,
        stream_sequence=1,
        turn_token=2,
        streaming_generation=None,
        wire_format=DownlinkAudioFormat("opus", 24_000, 1, 20.0),
        session_id="session",
        started_at_ns=0,
    )
    assert context is not None
    assert coordinator.offer_payload_nowait(
        connection_generation=5,
        stream_sequence=1,
        payload=b"opus",
        received_at_ns=1_000_000,
    )
    assert coordinator.end_stream_nowait(
        connection_generation=5,
        stream_sequence=1,
        reason="tts_stop",
        at_ns=2_000_000,
    )
    now_ns = 100_000_000
    await asyncio.sleep(0.15)
    assert not any(isinstance(event, RuntimePlaybackFailed) for event in events)
    await coordinator.close_generation(5, "test_complete")
