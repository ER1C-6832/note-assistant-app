"""Track asynchronous application work and provide bounded shutdown."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any

AsyncCloser = Callable[[], Awaitable[None]]


class ApplicationLifecycle:
    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[Any]] = set()
        self._closers: list[tuple[str, AsyncCloser]] = []
        self._closing = False
        self._closed = False

    @property
    def is_closing(self) -> bool:
        return self._closing

    @property
    def is_closed(self) -> bool:
        return self._closed

    def create_task(self, coroutine: Coroutine[Any, Any, Any], *, name: str) -> asyncio.Task[Any]:
        if self._closing:
            coroutine.close()
            raise RuntimeError("Application shutdown has started; new tasks are rejected.")

        task = asyncio.create_task(coroutine, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    def register_async_closer(self, name: str, closer: AsyncCloser) -> None:
        if self._closing:
            raise RuntimeError("Application shutdown has started; new closers are rejected.")
        self._closers.append((name, closer))

    async def shutdown(self, *, timeout_seconds: float = 1.0) -> None:
        if self._closed:
            return

        self._closing = True
        tasks = tuple(task for task in self._tasks if not task.done())
        for task in tasks:
            task.cancel()

        async def finish() -> None:
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            for _, closer in reversed(self._closers):
                await closer()

        try:
            await asyncio.wait_for(finish(), timeout=max(timeout_seconds, 0.01))
        finally:
            self._tasks.clear()
            self._closers.clear()
            self._closed = True
