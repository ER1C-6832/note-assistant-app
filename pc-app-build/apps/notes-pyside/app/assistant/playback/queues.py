"""Bounded encoded and PCM queues for Gate 4.1 playback."""

from __future__ import annotations

import asyncio
import threading
from collections import deque
from dataclasses import dataclass

from .models import EncodedDownlinkPacket, PcmAudioFormat


@dataclass(frozen=True, slots=True)
class EncodedInputTerminal:
    reason: str
    at_ns: int


class BoundedEncodedDownlinkQueue:
    """Async queue with packet capacity plus one reserved terminal slot."""

    def __init__(self, packet_capacity: int) -> None:
        if packet_capacity <= 0:
            raise ValueError("packet_capacity must be positive")
        self._packet_capacity = packet_capacity
        self._queue: asyncio.Queue[EncodedDownlinkPacket | EncodedInputTerminal] = asyncio.Queue(
            maxsize=packet_capacity + 1
        )
        self._packet_count = 0
        self._terminal_enqueued = False
        self._closed = False

    @property
    def packet_capacity(self) -> int:
        return self._packet_capacity

    @property
    def packet_count(self) -> int:
        return self._packet_count

    @property
    def empty(self) -> bool:
        return self._queue.empty()

    @property
    def terminal_enqueued(self) -> bool:
        return self._terminal_enqueued

    def offer(self, packet: EncodedDownlinkPacket) -> bool:
        if self._closed or self._terminal_enqueued:
            return False
        if self._packet_count >= self._packet_capacity:
            return False
        self._queue.put_nowait(packet)
        self._packet_count += 1
        return True

    def end(self, reason: str, at_ns: int) -> bool:
        if self._closed or self._terminal_enqueued:
            return False
        self._terminal_enqueued = True
        self._queue.put_nowait(EncodedInputTerminal(reason=reason, at_ns=at_ns))
        return True

    async def get(self) -> EncodedDownlinkPacket | EncodedInputTerminal:
        return await self._queue.get()

    def task_done(self, item: EncodedDownlinkPacket | EncodedInputTerminal) -> None:
        if isinstance(item, EncodedDownlinkPacket):
            self._packet_count = max(0, self._packet_count - 1)
        self._queue.task_done()

    def clear(self) -> None:
        self._closed = True
        while True:
            try:
                item = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if isinstance(item, EncodedDownlinkPacket):
                self._packet_count = max(0, self._packet_count - 1)
            self._queue.task_done()


class PcmPlaybackBuffer:
    """Thread-safe bounded PCM buffer with non-blocking callback consumption."""

    def __init__(self, pcm_format: PcmAudioFormat, capacity_bytes: int) -> None:
        if capacity_bytes <= 0:
            raise ValueError("capacity_bytes must be positive")
        if capacity_bytes % pcm_format.frame_size_bytes:
            raise ValueError("capacity_bytes must be PCM frame aligned")
        self._pcm_format = pcm_format
        self._capacity_bytes = capacity_bytes
        self._chunks: deque[bytes] = deque()
        self._head_offset = 0
        self._buffered_bytes = 0
        self._peak_bytes = 0
        self._terminal = False
        self._cancelled = False
        self._underflow_count = 0
        self._lock = threading.Lock()

    @property
    def pcm_format(self) -> PcmAudioFormat:
        return self._pcm_format

    @property
    def capacity_bytes(self) -> int:
        return self._capacity_bytes

    @property
    def buffered_bytes(self) -> int:
        with self._lock:
            return self._buffered_bytes

    @property
    def peak_bytes(self) -> int:
        with self._lock:
            return self._peak_bytes

    @property
    def underflow_count(self) -> int:
        with self._lock:
            return self._underflow_count

    @property
    def terminal_and_empty(self) -> bool:
        with self._lock:
            return self._terminal and self._buffered_bytes == 0 and not self._cancelled

    @property
    def cancelled(self) -> bool:
        with self._lock:
            return self._cancelled

    def offer(self, payload: bytes) -> bool:
        if not payload or len(payload) % self._pcm_format.frame_size_bytes:
            raise ValueError("PCM payload must be non-empty and frame aligned")
        with self._lock:
            if self._terminal or self._cancelled:
                return False
            if self._buffered_bytes + len(payload) > self._capacity_bytes:
                return False
            self._chunks.append(payload)
            self._buffered_bytes += len(payload)
            self._peak_bytes = max(self._peak_bytes, self._buffered_bytes)
            return True

    def consume(self, maximum_bytes: int) -> bytes:
        aligned = maximum_bytes - (maximum_bytes % self._pcm_format.frame_size_bytes)
        if aligned <= 0:
            return b""
        with self._lock:
            if self._cancelled:
                return b""
            if self._buffered_bytes == 0:
                if not self._terminal:
                    self._underflow_count += 1
                return b""
            remaining = min(aligned, self._buffered_bytes)
            parts: list[bytes] = []
            while remaining > 0 and self._chunks:
                head = self._chunks[0]
                available = len(head) - self._head_offset
                take = min(remaining, available)
                start = self._head_offset
                parts.append(head[start : start + take])
                self._head_offset += take
                self._buffered_bytes -= take
                remaining -= take
                if self._head_offset == len(head):
                    self._chunks.popleft()
                    self._head_offset = 0
            return b"".join(parts)

    def mark_terminal(self) -> None:
        with self._lock:
            if not self._cancelled:
                self._terminal = True

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True
            self._terminal = False
            self._chunks.clear()
            self._head_offset = 0
            self._buffered_bytes = 0
