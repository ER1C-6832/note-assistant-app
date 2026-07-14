"""Serialize blocking database work outside the Qt/qasync thread."""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class DatabaseExecutorClosedError(RuntimeError):
    pass


class DatabaseExecutor:
    def __init__(self, *, thread_name_prefix: str = "note-db") -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=thread_name_prefix)
        self._state_lock = threading.Lock()
        self._closed_event = threading.Event()
        self._closing = False
        self._closed = False

    @property
    def is_closing(self) -> bool:
        with self._state_lock:
            return self._closing

    @property
    def is_closed(self) -> bool:
        with self._state_lock:
            return self._closed

    async def run(self, operation: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
        loop = asyncio.get_running_loop()
        with self._state_lock:
            if self._closing or self._closed:
                raise DatabaseExecutorClosedError("database executor is closing or closed")
            future = loop.run_in_executor(
                self._executor,
                partial(operation, *args, **kwargs),
            )
        return await future

    async def close(self) -> None:
        loop = asyncio.get_running_loop()
        with self._state_lock:
            if self._closed:
                return
            owns_shutdown = not self._closing
            self._closing = True

        if not owns_shutdown:
            await loop.run_in_executor(None, self._closed_event.wait)
            return

        try:
            await loop.run_in_executor(
                None,
                partial(self._executor.shutdown, wait=True, cancel_futures=True),
            )
        finally:
            with self._state_lock:
                self._closed = True
            self._closed_event.set()
