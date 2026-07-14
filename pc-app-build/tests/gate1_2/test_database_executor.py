from __future__ import annotations

import asyncio
import threading
import time

import pytest

from app.notes import DatabaseExecutor, DatabaseExecutorClosedError


@pytest.mark.asyncio
async def test_executor_uses_one_worker_and_serializes_operations() -> None:
    executor = DatabaseExecutor()
    active = 0
    maximum_active = 0
    lock = threading.Lock()
    thread_ids: list[int] = []

    def work(value: int) -> int:
        nonlocal active, maximum_active
        with lock:
            active += 1
            maximum_active = max(maximum_active, active)
        thread_ids.append(threading.get_ident())
        time.sleep(0.02)
        with lock:
            active -= 1
        return value

    try:
        results = await asyncio.gather(
            *(executor.run(work, value) for value in range(5))
        )
    finally:
        await executor.close()

    assert results == [0, 1, 2, 3, 4]
    assert maximum_active == 1
    assert len(set(thread_ids)) == 1


@pytest.mark.asyncio
async def test_executor_rejects_work_after_close() -> None:
    executor = DatabaseExecutor()
    await executor.close()
    with pytest.raises(DatabaseExecutorClosedError):
        await executor.run(lambda: None)


@pytest.mark.asyncio
async def test_concurrent_close_calls_wait_for_the_same_shutdown() -> None:
    executor = DatabaseExecutor()
    await executor.run(lambda: None)
    await asyncio.gather(executor.close(), executor.close())
    assert executor.is_closed is True
