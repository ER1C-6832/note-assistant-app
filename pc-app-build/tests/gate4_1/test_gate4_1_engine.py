from __future__ import annotations

import asyncio

import pytest

from app.assistant.playback import (
    AssistantPlaybackEngine,
    DeterministicFakeOpusDecoder,
    EncodedDownlinkPacket,
    GateControlledFakeAudioOutput,
    PlaybackCancelledSignal,
    PlaybackEndedSignal,
    PlaybackFailedSignal,
    PlaybackLifecycleState,
    PlaybackStartedSignal,
    TtsStreamContext,
)
from app.assistant.protocol import DownlinkAudioFormat


class Clock:
    def __init__(self) -> None:
        self.value = 1_000

    def now_ns(self) -> int:
        self.value += 1_000
        return self.value


def _context() -> TtsStreamContext:
    return TtsStreamContext(
        connection_generation=7,
        stream_sequence=3,
        playback_generation=11,
        turn_token=5,
        streaming_generation=2,
        wire_format=DownlinkAudioFormat(
            codec="opus",
            sample_rate_hz=24_000,
            channels=1,
            frame_duration_ms=20.0,
        ),
        started_at_ns=100,
        session_id="not-exported",
    )


def _packet(sequence: int, payload: bytes | None = None) -> EncodedDownlinkPacket:
    return EncodedDownlinkPacket(
        connection_generation=7,
        stream_sequence=3,
        packet_sequence=sequence,
        received_at_ns=200 + sequence,
        payload=payload or f"packet-{sequence}".encode(),
    )


def _engine(
    *,
    gate: asyncio.Event | None = None,
    decoder_factory=None,
    encoded_budget_ms: int = 2_000,
    pcm_budget_ms: int = 2_000,
    startup_prebuffer_chunks: int = 2,
):
    clock = Clock()
    signals = []
    outputs = []

    async def sink(signal) -> None:
        signals.append(signal)

    def output_factory():
        output = GateControlledFakeAudioOutput(
            consume_gate=gate,
            chunk_bytes=3_840,
        )
        outputs.append(output)
        return output

    engine = AssistantPlaybackEngine(
        decoder_factory=decoder_factory
        or (lambda context: DeterministicFakeOpusDecoder(clock_ns=clock.now_ns)),
        output_factory=output_factory,
        event_sink=sink,
        clock_ns=clock.now_ns,
        encoded_budget_ms=encoded_budget_ms,
        pcm_budget_ms=pcm_budget_ms,
        startup_prebuffer_chunks=startup_prebuffer_chunks,
    )
    return engine, signals, outputs


@pytest.mark.asyncio
async def test_early_packets_before_start_are_played_and_drain_once() -> None:
    engine, signals, outputs = _engine()
    await engine.arm(_context())
    assert engine.offer_packet(_packet(1)) is True
    assert engine.offer_packet(_packet(2)) is True
    assert engine.end_stream(3, reason="tts_stop", at_ns=300) is True

    await engine.start(11)
    terminal = await engine.wait_finished()

    assert isinstance(terminal, PlaybackEndedSignal)
    assert [type(signal) for signal in signals] == [
        PlaybackStartedSignal,
        PlaybackEndedSignal,
    ]
    assert terminal.summary.encoded_packets_received == 2
    assert terminal.summary.decoded_sample_frames == 1_920
    assert terminal.summary.played_sample_frames == 1_920
    assert terminal.summary.natural_end is True
    assert outputs[0].consumed_bytes > 0
    assert engine.lifecycle is PlaybackLifecycleState.DRAINED
    assert engine.task_running is False
    assert engine.output_running is False
    await engine.close()


@pytest.mark.asyncio
async def test_playback_started_and_ended_wait_for_real_fake_consumption() -> None:
    gate = asyncio.Event()
    engine, signals, _ = _engine(gate=gate, startup_prebuffer_chunks=1)
    await engine.arm(_context())
    await engine.start(11)
    assert engine.offer_packet(_packet(1)) is True
    assert engine.end_stream(3, reason="tts_stop", at_ns=300) is True

    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert signals == []
    assert engine.lifecycle is PlaybackLifecycleState.BUFFERING

    gate.set()
    terminal = await engine.wait_finished()
    assert isinstance(terminal, PlaybackEndedSignal)
    assert isinstance(signals[0], PlaybackStartedSignal)
    assert isinstance(signals[1], PlaybackEndedSignal)
    await engine.close()


@pytest.mark.asyncio
async def test_corrupt_packet_fails_without_natural_playback_end() -> None:
    engine, signals, _ = _engine(startup_prebuffer_chunks=1)
    await engine.arm(_context())
    await engine.start(11)
    assert engine.offer_packet(_packet(1, b"CORRUPT-opus")) is True
    engine.end_stream(3, reason="tts_stop", at_ns=300)

    terminal = await engine.wait_finished()
    assert isinstance(terminal, PlaybackFailedSignal)
    assert terminal.code == "playback_worker_failed"
    assert not any(isinstance(item, PlaybackEndedSignal) for item in signals)
    assert engine.lifecycle is PlaybackLifecycleState.FAILED
    await engine.close()


@pytest.mark.asyncio
async def test_encoded_overflow_fails_current_stream_without_drop_oldest() -> None:
    engine, signals, _ = _engine(encoded_budget_ms=20, startup_prebuffer_chunks=1)
    await engine.arm(_context())
    assert engine.offer_packet(_packet(1)) is True
    assert engine.offer_packet(_packet(2)) is False

    terminal = await engine.wait_finished()
    assert isinstance(terminal, PlaybackFailedSignal)
    assert terminal.code == "downlink_overflow"
    assert engine.metrics.encoded_overflow_count == 1
    assert not any(isinstance(item, PlaybackEndedSignal) for item in signals)
    await engine.close()


@pytest.mark.asyncio
async def test_cancel_before_start_is_idempotent_and_not_natural_end() -> None:
    engine, signals, _ = _engine()
    await engine.arm(_context())
    assert engine.offer_packet(_packet(1)) is True

    first = await engine.cancel("user_stop")
    second = await engine.cancel("duplicate_stop")
    terminal = await engine.wait_finished()

    assert isinstance(first, PlaybackCancelledSignal)
    assert second is None
    assert terminal is first
    assert [type(signal) for signal in signals] == [PlaybackCancelledSignal]
    assert engine.pcm_buffered_bytes == 0
    assert engine.encoded_packet_count == 0
    await engine.close()


@pytest.mark.asyncio
async def test_stale_and_duplicate_terminal_are_harmless() -> None:
    engine, signals, _ = _engine(startup_prebuffer_chunks=1)
    await engine.arm(_context())
    stale = EncodedDownlinkPacket(
        connection_generation=6,
        stream_sequence=3,
        packet_sequence=1,
        received_at_ns=201,
        payload=b"stale",
    )
    assert engine.offer_packet(stale) is False
    assert engine.offer_packet(_packet(1)) is True
    assert engine.end_stream(3, reason="tts_stop", at_ns=300) is True
    assert engine.end_stream(3, reason="duplicate", at_ns=301) is False
    await engine.start(11)

    terminal = await engine.wait_finished()
    assert isinstance(terminal, PlaybackEndedSignal)
    assert engine.metrics.stale_packet_count == 1
    assert sum(isinstance(item, PlaybackEndedSignal) for item in signals) == 1
    await engine.close()


@pytest.mark.asyncio
async def test_zero_audio_response_never_forges_playback_ended() -> None:
    engine, signals, _ = _engine(
        decoder_factory=lambda context: DeterministicFakeOpusDecoder(emit_audio=False),
        startup_prebuffer_chunks=1,
    )
    await engine.arm(_context())
    await engine.start(11)
    assert engine.offer_packet(_packet(1)) is True
    assert engine.end_stream(3, reason="tts_stop", at_ns=300) is True

    terminal = await engine.wait_finished()
    assert isinstance(terminal, PlaybackFailedSignal)
    assert terminal.code == "playback_no_audio"
    assert not any(isinstance(item, PlaybackStartedSignal) for item in signals)
    assert not any(isinstance(item, PlaybackEndedSignal) for item in signals)
    await engine.close()


@pytest.mark.asyncio
async def test_pcm_overflow_fails_without_partial_natural_end() -> None:
    engine, signals, _ = _engine(pcm_budget_ms=10, startup_prebuffer_chunks=1)
    await engine.arm(_context())
    await engine.start(11)
    assert engine.offer_packet(_packet(1)) is True

    terminal = await engine.wait_finished()
    assert isinstance(terminal, PlaybackFailedSignal)
    assert terminal.code == "pcm_overflow"
    assert engine.metrics.pcm_overflow_count == 1
    assert not any(isinstance(item, PlaybackEndedSignal) for item in signals)
    await engine.close()


@pytest.mark.asyncio
async def test_cancel_during_playing_stops_output_without_natural_end() -> None:
    engine, signals, _ = _engine(startup_prebuffer_chunks=1)
    await engine.arm(_context())
    await engine.start(11)
    for sequence in range(1, 5):
        assert engine.offer_packet(_packet(sequence)) is True

    for _ in range(20):
        if any(isinstance(item, PlaybackStartedSignal) for item in signals):
            break
        await asyncio.sleep(0)
    assert any(isinstance(item, PlaybackStartedSignal) for item in signals)

    cancelled = await engine.cancel("user_stop_during_playback")
    assert isinstance(cancelled, PlaybackCancelledSignal)
    assert not any(isinstance(item, PlaybackEndedSignal) for item in signals)
    assert engine.task_running is False
    assert engine.output_running is False
    await engine.close()


@pytest.mark.asyncio
async def test_close_is_idempotent_and_leaves_no_worker_or_output() -> None:
    engine, signals, _ = _engine()
    await engine.arm(_context())
    await engine.start(11)
    await engine.close()
    await engine.close()

    assert sum(isinstance(item, PlaybackCancelledSignal) for item in signals) == 1
    assert engine.lifecycle is PlaybackLifecycleState.CLOSED
    assert engine.task_running is False
    assert engine.output_running is False
