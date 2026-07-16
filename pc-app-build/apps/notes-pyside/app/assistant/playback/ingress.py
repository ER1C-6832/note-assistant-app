"""Non-blocking bounded ingress separated from the playback worker."""

from __future__ import annotations

from enum import Enum

from .models import EncodedDownlinkPacket, TtsStreamContext
from .queues import BoundedEncodedDownlinkQueue


class IngressOfferStatus(str, Enum):
    ACCEPTED = "accepted"
    STALE = "stale"
    OVERFLOW = "overflow"
    TERMINAL = "terminal"


class DownlinkAudioIngress:
    """Own wire correlation and bounded packet staging for one TTS stream."""

    def __init__(self, context: TtsStreamContext, *, packet_capacity: int) -> None:
        self._context = context
        self._queue = BoundedEncodedDownlinkQueue(packet_capacity)
        self._last_packet_sequence = 0
        self._aborted = False

    @property
    def queue(self) -> BoundedEncodedDownlinkQueue:
        return self._queue

    @property
    def packet_count(self) -> int:
        return self._queue.packet_count

    @property
    def terminal(self) -> bool:
        return self._queue.terminal_enqueued

    def offer(self, packet: EncodedDownlinkPacket) -> IngressOfferStatus:
        if self._aborted or self._queue.terminal_enqueued:
            return IngressOfferStatus.TERMINAL
        if (
            packet.connection_generation != self._context.connection_generation
            or packet.stream_sequence != self._context.stream_sequence
            or packet.packet_sequence <= self._last_packet_sequence
        ):
            return IngressOfferStatus.STALE
        if not self._queue.offer(packet):
            return IngressOfferStatus.OVERFLOW
        self._last_packet_sequence = packet.packet_sequence
        return IngressOfferStatus.ACCEPTED

    def end(
        self,
        *,
        connection_generation: int,
        stream_sequence: int,
        reason: str,
        at_ns: int,
    ) -> bool:
        if self._aborted:
            return False
        if (
            connection_generation != self._context.connection_generation
            or stream_sequence != self._context.stream_sequence
        ):
            return False
        return self._queue.end(reason=reason, at_ns=at_ns)

    def abort(self) -> None:
        if self._aborted:
            return
        self._aborted = True
        self._queue.clear()
