"""Bounded, thread-safe queues with explicit Gate 3 overflow semantics."""

from __future__ import annotations

import queue
import threading
from collections import deque
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


class AudioQueueClosed(RuntimeError):
    pass


class AudioQueueOverflow(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AudioQueueStats:
    accepted: int = 0
    removed: int = 0
    dropped_oldest: int = 0
    overflow_failures: int = 0


class DropOldestAudioQueue(Generic[T]):
    """Never blocks a callback; discards the oldest item when full."""

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._capacity = capacity
        self._items: deque[T] = deque()
        self._condition = threading.Condition()
        self._closed = False
        self._accepted = 0
        self._removed = 0
        self._dropped_oldest = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    def put(self, item: T) -> T | None:
        with self._condition:
            if self._closed:
                raise AudioQueueClosed("audio queue is closed")
            dropped = None
            if len(self._items) >= self._capacity:
                dropped = self._items.popleft()
                self._dropped_oldest += 1
            self._items.append(item)
            self._accepted += 1
            self._condition.notify()
            return dropped

    def get(self, timeout: float | None = None) -> T:
        with self._condition:
            if timeout is not None and timeout < 0:
                raise ValueError("timeout cannot be negative")
            if not self._items and not self._closed:
                self._condition.wait(timeout)
            if self._items:
                self._removed += 1
                return self._items.popleft()
            if self._closed:
                raise AudioQueueClosed("audio queue is closed")
            raise queue.Empty

    def drain(self) -> tuple[T, ...]:
        with self._condition:
            drained = tuple(self._items)
            self._removed += len(drained)
            self._items.clear()
            return drained

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()

    def __len__(self) -> int:
        with self._condition:
            return len(self._items)

    @property
    def stats(self) -> AudioQueueStats:
        with self._condition:
            return AudioQueueStats(
                accepted=self._accepted,
                removed=self._removed,
                dropped_oldest=self._dropped_oldest,
            )


class FailOnOverflowAudioQueue(Generic[T]):
    """Reject overflow so the current turn can fail visibly."""

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._capacity = capacity
        self._items: deque[T] = deque()
        self._condition = threading.Condition()
        self._closed = False
        self._accepted = 0
        self._removed = 0
        self._overflow_failures = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    def put(self, item: T) -> None:
        with self._condition:
            if self._closed:
                raise AudioQueueClosed("audio queue is closed")
            if len(self._items) >= self._capacity:
                self._overflow_failures += 1
                raise AudioQueueOverflow("encoded audio queue capacity exceeded")
            self._items.append(item)
            self._accepted += 1
            self._condition.notify()

    def get(self, timeout: float | None = None) -> T:
        with self._condition:
            if timeout is not None and timeout < 0:
                raise ValueError("timeout cannot be negative")
            if not self._items and not self._closed:
                self._condition.wait(timeout)
            if self._items:
                self._removed += 1
                return self._items.popleft()
            if self._closed:
                raise AudioQueueClosed("audio queue is closed")
            raise queue.Empty

    def drain(self) -> tuple[T, ...]:
        with self._condition:
            drained = tuple(self._items)
            self._removed += len(drained)
            self._items.clear()
            return drained

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()

    def __len__(self) -> int:
        with self._condition:
            return len(self._items)

    @property
    def stats(self) -> AudioQueueStats:
        with self._condition:
            return AudioQueueStats(
                accepted=self._accepted,
                removed=self._removed,
                overflow_failures=self._overflow_failures,
            )
