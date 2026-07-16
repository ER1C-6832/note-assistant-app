from __future__ import annotations

import pytest

from app.assistant.network.downlink_probe import (
    MetadataOnlyDownlinkProbe,
    ProbeDecodeResult,
)
from app.assistant.protocol.events import DownlinkAudioFormat


class FakeDecoder:
    def __init__(self) -> None:
        self.payload_lengths: list[int] = []
        self.closed = False

    def decode(self, payload: bytes, audio_format: DownlinkAudioFormat):
        self.payload_lengths.append(len(payload))
        return ProbeDecodeResult(
            sample_rate_hz=audio_format.sample_rate_hz,
            channels=audio_format.channels,
            sample_count=960,
        )

    def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_probe_records_metadata_decodes_and_never_exposes_payload() -> None:
    decoder = FakeDecoder()
    probe = MetadataOnlyDownlinkProbe(decoder=decoder, packet_capacity=4)
    audio_format = DownlinkAudioFormat("opus", 48_000, 1, 20.0)

    await probe.open_generation(7)
    probe.observe_server_hello(7, audio_format, None)
    probe.observe_tts_state(7, "start", 100)
    assert probe.offer_packet_nowait(7, b"private-opus-payload", 120)
    probe.observe_tts_state(7, "stop", 140)
    await probe.close_generation(7)

    snapshot = probe.snapshot()
    public = snapshot.as_public_dict()
    assert snapshot.binary_packet_count == 1
    assert snapshot.decoded == ProbeDecodeResult(48_000, 1, 960)
    assert snapshot.first_binary_relative_to_terminal == "before"
    assert snapshot.last_binary_relative_to_terminal == "before"
    assert snapshot.payload_persisted is False
    assert snapshot.secrets_redacted is True
    assert snapshot.task_running is False
    assert decoder.payload_lengths == [20]
    assert decoder.closed is True
    assert b"private-opus-payload" not in repr(public).encode()
    assert not _contains_bytes(public)


@pytest.mark.asyncio
async def test_probe_preserves_terminal_to_last_binary_ordering_sample() -> None:
    probe = MetadataOnlyDownlinkProbe(decoder=FakeDecoder(), packet_capacity=2)
    audio_format = DownlinkAudioFormat("opus", 16_000, 1, 20.0)
    await probe.open_generation(6)
    probe.observe_server_hello(6, audio_format, None)
    probe.observe_tts_state(6, "start", 10)
    probe.observe_tts_state(6, "stop", 20)

    assert probe.offer_packet_nowait(6, b"late-wire-packet", 30)
    await probe.close_generation(6)

    snapshot = probe.snapshot()
    assert snapshot.observed_terminal is True
    assert snapshot.last_binary_relative_to_terminal == "after"
    assert snapshot.decoded is not None


@pytest.mark.asyncio
async def test_probe_rejects_unarmed_and_stale_binary() -> None:
    probe = MetadataOnlyDownlinkProbe(decoder=FakeDecoder(), packet_capacity=2)
    await probe.open_generation(3)

    assert not probe.offer_packet_nowait(2, b"stale", 10)
    assert not probe.offer_packet_nowait(3, b"unarmed", 11)
    await probe.close_generation(3)

    snapshot = probe.snapshot()
    assert snapshot.stale_event_count == 1
    assert snapshot.unarmed_binary_count == 1
    assert snapshot.binary_packet_count == 1


@pytest.mark.asyncio
async def test_probe_queue_is_bounded_and_overflow_is_visible() -> None:
    probe = MetadataOnlyDownlinkProbe(decoder=FakeDecoder(), packet_capacity=1)
    audio_format = DownlinkAudioFormat("opus", 16_000, 1, 20.0)
    await probe.open_generation(5)
    probe.observe_server_hello(5, audio_format, None)
    probe.observe_tts_state(5, "start", 1)

    first = probe.offer_packet_nowait(5, b"a", 2)
    second = probe.offer_packet_nowait(5, b"b", 3)
    assert first is True
    assert second is False
    probe.observe_tts_state(5, "stop", 4)
    await probe.close_generation(5)

    assert probe.snapshot().queue_overflow_count == 1


def _contains_bytes(value: object) -> bool:
    if isinstance(value, bytes):
        return True
    if isinstance(value, dict):
        return any(_contains_bytes(key) or _contains_bytes(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_bytes(item) for item in value)
    return False
