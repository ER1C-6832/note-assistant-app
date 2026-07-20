from __future__ import annotations

import math
import struct

import pytest

from app.assistant.audio import (
    AssistantAudioEngine,
    FakeCaptureScript,
    FakeOpusEncoder,
    PcmFrame,
    ScriptedFakeAudioCapture,
)
from app.assistant.audio.barge_in import (
    MONITOR_FORMAT_20_MS,
    _normalize_to_mono_16k_20ms,
    _split_10_ms,
)


@pytest.mark.parametrize("rate,channels", [(16_000, 1), (24_000, 1), (44_100, 2), (48_000, 2)])
def test_render_reference_is_normalized_to_exact_apm_blocks(rate: int, channels: int) -> None:
    frame_count = rate // 50
    samples: list[int] = []
    for index in range(frame_count):
        value = round(800 * math.sin(index / max(1, frame_count) * math.tau))
        samples.extend([value] * channels)
    source = struct.pack("<" + "h" * len(samples), *samples)

    normalized = _normalize_to_mono_16k_20ms(source, rate, channels)
    first, second = _split_10_ms(normalized)

    assert len(normalized) == MONITOR_FORMAT_20_MS.bytes_per_frame
    assert len(first) == len(second) == 320


def test_invalid_render_reference_fails_closed() -> None:
    with pytest.raises(ValueError):
        _normalize_to_mono_16k_20ms(b"bad", 48_000, 2)


@pytest.mark.asyncio
async def test_processed_pre_roll_is_first_audio_of_promoted_capture() -> None:
    capture = ScriptedFakeAudioCapture(FakeCaptureScript.from_frames(()))
    engine = AssistantAudioEngine(capture=capture, encoder_factory=FakeOpusEncoder)
    payload = struct.pack("<320h", *([700] * 320))
    engine.stage_processed_pre_roll(
        5,
        (
            PcmFrame(generation=99, sequence=40, captured_at_ns=10, pcm16_le=payload),
            PcmFrame(generation=99, sequence=41, captured_at_ns=20, pcm16_le=payload),
        ),
    )

    await engine.start_capture(5, requested_at_ns=0)
    first = await engine.next_packet(5)
    second = await engine.next_packet(5)
    assert first is not None and second is not None
    assert (first.generation, first.sequence) == (5, 0)
    assert (second.generation, second.sequence) == (5, 1)

    await engine.cancel_capture(5, reason="test")
    await engine.finish_generation(5)
    await engine.close()
