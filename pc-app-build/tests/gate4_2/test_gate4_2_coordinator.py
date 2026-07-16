from __future__ import annotations

import asyncio

import pytest

from app.assistant.playback import (
    AssistantPlaybackEngine,
    DeterministicFakeOpusDecoder,
    GateControlledFakeAudioOutput,
    PcmAudioFormat,
    PlaybackCoordinator,
    PyAudioOutputPlan,
)
from app.assistant.playback.runtime_events import (
    ActualPlaybackEnded,
    ActualPlaybackStarted,
    PlaybackProgressUpdated,
)
from app.assistant.protocol import DownlinkAudioFormat


@pytest.mark.asyncio
async def test_coordinator_runs_one_realistic_stream_to_physical_drain() -> None:
    now = 0

    def clock_ns() -> int:
        nonlocal now
        now += 1_000_000
        return now

    output = GateControlledFakeAudioOutput(chunk_bytes=3_840)
    plan = PyAudioOutputPlan(0, "Fake output", PcmAudioFormat(48_000, 2), 960)

    def engine_factory(context, selected, sink):
        assert selected == plan
        return AssistantPlaybackEngine(
            decoder_factory=lambda _context: DeterministicFakeOpusDecoder(
                pcm_format=selected.pcm_format,
                clock_ns=clock_ns,
            ),
            output_factory=lambda: output,
            event_sink=sink,
            clock_ns=clock_ns,
            startup_prebuffer_chunks=1,
            drain_timeout_seconds=1.0,
        )

    events = []

    async def sink(event) -> None:
        events.append(event)

    coordinator = PlaybackCoordinator(
        clock_ns=clock_ns,
        output_plan_provider=lambda: plan,
        engine_factory=engine_factory,
    )
    await coordinator.open_generation(7, sink)
    context = await coordinator.begin_stream(
        connection_generation=7,
        stream_sequence=1,
        turn_token=3,
        streaming_generation=2,
        wire_format=DownlinkAudioFormat("opus", 24_000, 1, 20.0),
        session_id="session",
        started_at_ns=clock_ns(),
    )
    assert context is not None
    assert coordinator.offer_payload_nowait(
        connection_generation=7,
        stream_sequence=1,
        payload=b"packet-one",
        received_at_ns=clock_ns(),
    )
    assert await coordinator.start_playback(
        connection_generation=7,
        stream_sequence=1,
        playback_generation=1,
    )
    assert coordinator.end_stream_nowait(
        connection_generation=7,
        stream_sequence=1,
        reason="tts_stop",
        at_ns=clock_ns(),
    )

    for _ in range(100):
        if any(isinstance(item, ActualPlaybackEnded) for item in events):
            break
        await asyncio.sleep(0.001)

    assert sum(isinstance(item, ActualPlaybackStarted) for item in events) == 1
    assert sum(isinstance(item, ActualPlaybackEnded) for item in events) == 1
    assert any(isinstance(item, PlaybackProgressUpdated) for item in events)
    ended = next(item for item in events if isinstance(item, ActualPlaybackEnded))
    assert ended.summary.played_sample_frames == ended.summary.decoded_sample_frames
    assert ended.summary.played_sample_frames > 0
    assert coordinator.last_summary == ended.summary
    assert not coordinator.output_running
    await coordinator.close_generation(7, "test_complete")


@pytest.mark.asyncio
async def test_stale_generation_and_unarmed_binary_are_rejected() -> None:
    coordinator = PlaybackCoordinator(
        clock_ns=lambda: 1,
        output_plan_provider=lambda: PyAudioOutputPlan(0, "Fake", PcmAudioFormat(48_000, 2), 960),
    )
    await coordinator.open_generation(2, lambda event: asyncio.sleep(0))
    assert not coordinator.offer_payload_nowait(
        connection_generation=2,
        stream_sequence=1,
        payload=b"packet",
        received_at_ns=1,
    )
    assert (
        await coordinator.begin_stream(
            connection_generation=1,
            stream_sequence=1,
            turn_token=1,
            streaming_generation=None,
            wire_format=DownlinkAudioFormat("opus", 24_000, 1, 20.0),
            session_id=None,
            started_at_ns=1,
        )
        is None
    )


@pytest.mark.asyncio
async def test_stream_start_watchdog_fails_without_binary_and_leaks_no_task() -> None:
    now = 0

    def clock_ns() -> int:
        nonlocal now
        now += 1_000_000
        return now

    output = GateControlledFakeAudioOutput(chunk_bytes=3_840)
    plan = PyAudioOutputPlan(0, "Fake output", PcmAudioFormat(48_000, 2), 960)

    def engine_factory(context, selected, sink):
        return AssistantPlaybackEngine(
            decoder_factory=lambda _context: DeterministicFakeOpusDecoder(
                pcm_format=selected.pcm_format,
                clock_ns=clock_ns,
            ),
            output_factory=lambda: output,
            event_sink=sink,
            clock_ns=clock_ns,
            startup_prebuffer_chunks=1,
            drain_timeout_seconds=1.0,
        )

    events = []

    async def sink(event) -> None:
        events.append(event)

    coordinator = PlaybackCoordinator(
        clock_ns=clock_ns,
        output_plan_provider=lambda: plan,
        engine_factory=engine_factory,
        stream_start_timeout_seconds=0.001,
        decoder_progress_timeout_seconds=0.001,
    )
    await coordinator.open_generation(9, sink)
    context = await coordinator.begin_stream(
        connection_generation=9,
        stream_sequence=1,
        turn_token=4,
        streaming_generation=None,
        wire_format=DownlinkAudioFormat("opus", 24_000, 1, 20.0),
        session_id="session",
        started_at_ns=0,
    )
    assert context is not None
    assert await coordinator.start_playback(
        connection_generation=9,
        stream_sequence=1,
        playback_generation=1,
    )

    from app.assistant.playback.runtime_events import RuntimePlaybackFailed

    for _ in range(100):
        if any(isinstance(item, RuntimePlaybackFailed) for item in events):
            break
        await asyncio.sleep(0.002)

    failure = next(item for item in events if isinstance(item, RuntimePlaybackFailed))
    assert failure.code == "playback_stream_start_timeout"
    assert not coordinator.task_running
    assert not coordinator.output_running
    await coordinator.close_generation(9, "test_complete")


@pytest.mark.asyncio
async def test_output_open_failure_becomes_runtime_playback_failure() -> None:
    class FailingOpenOutput(GateControlledFakeAudioOutput):
        async def open(self, context, source, consumed_callback, drained_callback):
            del context, source, consumed_callback, drained_callback
            raise RuntimeError("output open failed")

    now = 0

    def clock_ns() -> int:
        nonlocal now
        now += 1_000_000
        return now

    plan = PyAudioOutputPlan(0, "Fake output", PcmAudioFormat(48_000, 2), 960)

    def engine_factory(context, selected, sink):
        return AssistantPlaybackEngine(
            decoder_factory=lambda _context: DeterministicFakeOpusDecoder(
                pcm_format=selected.pcm_format,
                clock_ns=clock_ns,
            ),
            output_factory=FailingOpenOutput,
            event_sink=sink,
            clock_ns=clock_ns,
        )

    events = []

    async def sink(event) -> None:
        events.append(event)

    coordinator = PlaybackCoordinator(
        clock_ns=clock_ns,
        output_plan_provider=lambda: plan,
        engine_factory=engine_factory,
    )
    await coordinator.open_generation(11, sink)
    context = await coordinator.begin_stream(
        connection_generation=11,
        stream_sequence=1,
        turn_token=8,
        streaming_generation=None,
        wire_format=DownlinkAudioFormat("opus", 24_000, 1, 20.0),
        session_id="session",
        started_at_ns=clock_ns(),
    )
    assert context is not None
    assert not await coordinator.start_playback(
        connection_generation=11,
        stream_sequence=1,
        playback_generation=1,
    )

    from app.assistant.playback.runtime_events import RuntimePlaybackFailed

    failure = next(item for item in events if isinstance(item, RuntimePlaybackFailed))
    assert failure.code == "playback_output_start_failed"
    assert "output open failed" in failure.message
    await coordinator.close_generation(11, "test_complete")
