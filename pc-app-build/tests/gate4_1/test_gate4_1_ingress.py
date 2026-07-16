from __future__ import annotations

from app.assistant.playback import (
    DownlinkAudioIngress,
    EncodedDownlinkPacket,
    IngressOfferStatus,
    TtsStreamContext,
)
from app.assistant.protocol import DownlinkAudioFormat


def _context() -> TtsStreamContext:
    return TtsStreamContext(
        connection_generation=4,
        stream_sequence=2,
        playback_generation=3,
        turn_token=5,
        streaming_generation=1,
        wire_format=DownlinkAudioFormat("opus", 24_000, 1, 20.0),
        started_at_ns=1,
    )


def _packet(connection: int, stream: int, sequence: int) -> EncodedDownlinkPacket:
    return EncodedDownlinkPacket(
        connection_generation=connection,
        stream_sequence=stream,
        packet_sequence=sequence,
        received_at_ns=sequence,
        payload=b"packet",
    )


def test_ingress_rejects_stale_identity_and_sequence() -> None:
    ingress = DownlinkAudioIngress(_context(), packet_capacity=2)
    assert ingress.offer(_packet(3, 2, 1)) is IngressOfferStatus.STALE
    assert ingress.offer(_packet(4, 1, 1)) is IngressOfferStatus.STALE
    assert ingress.offer(_packet(4, 2, 1)) is IngressOfferStatus.ACCEPTED
    assert ingress.offer(_packet(4, 2, 1)) is IngressOfferStatus.STALE


def test_ingress_is_bounded_without_drop_oldest() -> None:
    ingress = DownlinkAudioIngress(_context(), packet_capacity=1)
    first = _packet(4, 2, 1)
    second = _packet(4, 2, 2)
    assert ingress.offer(first) is IngressOfferStatus.ACCEPTED
    assert ingress.offer(second) is IngressOfferStatus.OVERFLOW
    assert ingress.packet_count == 1


def test_ingress_terminal_and_abort_are_idempotent() -> None:
    ingress = DownlinkAudioIngress(_context(), packet_capacity=2)
    assert ingress.end(
        connection_generation=4,
        stream_sequence=2,
        reason="tts_stop",
        at_ns=10,
    )
    assert not ingress.end(
        connection_generation=4,
        stream_sequence=2,
        reason="duplicate",
        at_ns=11,
    )
    assert ingress.offer(_packet(4, 2, 1)) is IngressOfferStatus.TERMINAL
    ingress.abort()
    ingress.abort()
    assert ingress.packet_count == 0
