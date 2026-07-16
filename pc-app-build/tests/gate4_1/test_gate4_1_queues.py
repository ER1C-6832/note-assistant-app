from __future__ import annotations

import pytest

from app.assistant.playback import (
    BoundedEncodedDownlinkQueue,
    EncodedDownlinkPacket,
    EncodedInputTerminal,
    PcmAudioFormat,
    PcmPlaybackBuffer,
)


def _packet(sequence: int) -> EncodedDownlinkPacket:
    return EncodedDownlinkPacket(
        connection_generation=1,
        stream_sequence=1,
        packet_sequence=sequence,
        received_at_ns=sequence,
        payload=b"packet",
    )


@pytest.mark.asyncio
async def test_encoded_queue_is_bounded_and_reserves_terminal_slot() -> None:
    queue = BoundedEncodedDownlinkQueue(packet_capacity=2)
    assert queue.offer(_packet(1)) is True
    assert queue.offer(_packet(2)) is True
    assert queue.offer(_packet(3)) is False
    assert queue.end("tts_stop", 10) is True
    assert queue.end("duplicate", 11) is False

    items = []
    for _ in range(3):
        item = await queue.get()
        items.append(item)
        queue.task_done(item)
    assert [type(item) for item in items] == [
        EncodedDownlinkPacket,
        EncodedDownlinkPacket,
        EncodedInputTerminal,
    ]
    assert queue.packet_count == 0


def test_pcm_buffer_partial_consumption_and_physical_drain() -> None:
    pcm_format = PcmAudioFormat(48_000, 2)
    buffer = PcmPlaybackBuffer(pcm_format, capacity_bytes=32)
    assert buffer.offer(b"\x01" * 16) is True
    assert buffer.offer(b"\x02" * 16) is True
    assert buffer.offer(b"\x03" * 4) is False

    assert buffer.consume(12) == b"\x01" * 12
    buffer.mark_terminal()
    assert buffer.terminal_and_empty is False
    assert buffer.consume(12) == b"\x01" * 4 + b"\x02" * 8
    assert buffer.consume(16) == b"\x02" * 8
    assert buffer.terminal_and_empty is True
    assert buffer.peak_bytes == 32


def test_pcm_underflow_and_cancel_do_not_create_natural_drain() -> None:
    buffer = PcmPlaybackBuffer(PcmAudioFormat(16_000, 1), capacity_bytes=64)
    assert buffer.consume(16) == b""
    assert buffer.underflow_count == 1
    buffer.cancel()
    assert buffer.consume(16) == b""
    assert buffer.terminal_and_empty is False
