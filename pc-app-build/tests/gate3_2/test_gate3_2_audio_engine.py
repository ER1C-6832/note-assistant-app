from __future__ import annotations

import asyncio
import struct

import pytest

from app.assistant.audio import (
    AssistantAudioEngine,
    AudioEngineBusyError,
    AudioEngineFailure,
    FakeCaptureScript,
    FakeOpusEncoder,
    ScriptedFakeAudioCapture,
)


def _frame(sample: int = 1200) -> bytes:
    return struct.pack("<320h", *([sample] * 320))


@pytest.mark.asyncio
async def test_shared_engine_encodes_and_reports_bounded_metrics() -> None:
    capture = ScriptedFakeAudioCapture(
        FakeCaptureScript.from_frames((_frame(), _frame(), _frame()))
    )
    engine = AssistantAudioEngine(capture=capture, encoder_factory=FakeOpusEncoder)
    await engine.start_capture(7, requested_at_ns=0)
    assert capture.emit_all() == 3

    packets = []
    for _ in range(3):
        packet = await asyncio.wait_for(engine.next_packet(7), timeout=1.0)
        assert packet is not None
        engine.mark_uploaded(packet, uploaded_at_ns=packet.encoded_at_ns + 1)
        packets.append(packet)

    summary = await engine.stop_capture(7)
    await engine.finish_generation(7)
    await engine.close()

    assert len(packets) == 3
    assert summary.captured_frames == 3
    assert summary.encoded_frames == 3
    assert summary.uploaded_frames == 3
    assert summary.speech_seen is True
    assert summary.stopped_within_budget is True
    assert engine.worker_alive is False


@pytest.mark.asyncio
async def test_engine_rejects_double_capture_and_stale_stop() -> None:
    capture = ScriptedFakeAudioCapture(FakeCaptureScript.from_frames((_frame(),)))
    engine = AssistantAudioEngine(capture=capture, encoder_factory=FakeOpusEncoder)
    await engine.start_capture(3, requested_at_ns=0)
    with pytest.raises(AudioEngineBusyError):
        await engine.start_capture(4, requested_at_ns=0)
    with pytest.raises(Exception):
        await engine.stop_capture(2)
    await engine.cancel_capture(3, reason="test")
    await engine.finish_generation(3)
    await engine.close()


@pytest.mark.asyncio
async def test_encoded_packet_overflow_fails_the_current_turn() -> None:
    capture = ScriptedFakeAudioCapture(
        FakeCaptureScript.from_frames(tuple(_frame() for _ in range(20)))
    )
    engine = AssistantAudioEngine(
        capture=capture,
        encoder_factory=FakeOpusEncoder,
        pcm_capacity=20,
        packet_capacity=1,
    )
    await engine.start_capture(9, requested_at_ns=0)
    capture.emit_all()
    await asyncio.sleep(0.1)
    with pytest.raises(AudioEngineFailure) as captured:
        await engine.next_packet(9)
    assert captured.value.code == "audio_uplink_overflow"
    await engine.cancel_capture(9, reason="overflow")
    await engine.finish_generation(9)
    await engine.close()


def test_real_av_adapter_emits_one_raw_opus_packet() -> None:
    pytest.importorskip("av")
    from app.assistant.audio import PcmFrame, PyAvOpusEncoder

    encoder = PyAvOpusEncoder()
    try:
        packet = encoder.encode(
            PcmFrame(
                generation=1,
                sequence=0,
                captured_at_ns=1,
                pcm16_le=_frame(100),
            )
        )
    finally:
        encoder.close()
    assert packet.payload
    assert len(packet.payload) < 4000


@pytest.mark.asyncio
async def test_capture_stop_failure_is_bounded_and_visible() -> None:
    class StopFailingCapture(ScriptedFakeAudioCapture):
        def stop(self, generation: int) -> None:
            super().stop(generation)
            raise RuntimeError("scripted stop failure")

    capture = StopFailingCapture(FakeCaptureScript.from_frames((_frame(),)))
    engine = AssistantAudioEngine(capture=capture, encoder_factory=FakeOpusEncoder)
    await engine.start_capture(12, requested_at_ns=0)
    capture.emit_all()
    await asyncio.sleep(0.05)
    summary = await engine.stop_capture(12)
    assert summary.stopped_within_budget is False
    assert summary.error_message == "scripted stop failure"
    assert engine.failure is not None
    assert engine.failure.code == "audio_capture_stop_failed"
    await engine.finish_generation(12)
    await engine.close()
