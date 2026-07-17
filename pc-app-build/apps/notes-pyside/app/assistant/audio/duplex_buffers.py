"""Small bounded PCM frame buffers for the supervised duplex foundation."""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass

from .gate6_contracts import TimedPcmFrame


@dataclass(frozen=True, slots=True)
class DuplexBufferStats:
    size: int
    capacity: int
    offered: int
    consumed: int
    overflow_count: int


class BoundedTimedPcmBuffer:
    """Keep newest real-time frames while making every overflow observable."""

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("duplex buffer capacity must be positive")
        self._capacity = int(capacity)
        self._items: deque[TimedPcmFrame] = deque()
        self._offered = 0
        self._consumed = 0
        self._overflow_count = 0
        self._lock = threading.RLock()

    def offer(self, frame: TimedPcmFrame) -> bool:
        with self._lock:
            self._offered += 1
            overflowed = len(self._items) >= self._capacity
            if overflowed:
                self._items.popleft()
                self._overflow_count += 1
            self._items.append(frame)
            return not overflowed

    def take_nowait(self) -> TimedPcmFrame | None:
        with self._lock:
            if not self._items:
                return None
            self._consumed += 1
            return self._items.popleft()

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    @property
    def stats(self) -> DuplexBufferStats:
        with self._lock:
            return DuplexBufferStats(
                size=len(self._items),
                capacity=self._capacity,
                offered=self._offered,
                consumed=self._consumed,
                overflow_count=self._overflow_count,
            )
