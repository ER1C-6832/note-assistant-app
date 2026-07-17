from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.assistant.mcp.confirmation import PendingConfirmationService
from app.assistant.mcp.contracts import ToolResult, ToolRisk


class FakeClock:
    def __init__(self) -> None:
        self.value = 100.0
        self.wall = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def monotonic(self) -> float:
        return self.value

    def now_utc(self) -> datetime:
        return self.wall

    def advance(self, seconds: float) -> None:
        self.value += seconds
        self.wall += timedelta(seconds=seconds)


async def _success(_pending) -> ToolResult:
    return ToolResult("success", "ok", "notes.delete", ToolRisk.HIGH)


@pytest.mark.asyncio
async def test_confirmation_is_session_bound_single_use_and_expiring() -> None:
    clock = FakeClock()
    service = PendingConfirmationService(capacity=2, ttl_seconds=10, clock=clock)
    pending = await service.create(
        connection_generation=3,
        session_id="session-a",
        tool_name="notes.delete",
        risk=ToolRisk.HIGH,
        arguments={"note_ids": [1]},
        preview={"operation": "soft_delete", "note_count": 1},
        affected_note_ids=(1,),
    )
    assert pending is not None

    wrong = await service.confirm(
        pending.confirmation_id,
        connection_generation=3,
        session_id="session-b",
        executor=_success,
    )
    assert wrong.error_code == "confirmation_context_mismatch"
    assert service.pending_count == 1

    rejected = await service.reject(
        pending.confirmation_id,
        connection_generation=3,
        session_id="session-a",
    )
    assert rejected.status == "rejected"
    repeated = await service.confirm(
        pending.confirmation_id,
        connection_generation=3,
        session_id="session-a",
        executor=_success,
    )
    assert repeated.error_code == "confirmation_consumed"

    expiring = await service.create(
        connection_generation=3,
        session_id="session-a",
        tool_name="tags.delete",
        risk=ToolRisk.HIGH,
        arguments={"name": "x"},
        preview={"operation": "delete_tag"},
    )
    assert expiring is not None
    clock.advance(11)
    listed = await service.list_for_context(connection_generation=3, session_id="session-a")
    assert listed == ()
    expired = await service.confirm(
        expiring.confirmation_id,
        connection_generation=3,
        session_id="session-a",
        executor=_success,
    )
    assert expired.error_code == "confirmation_expired"


@pytest.mark.asyncio
async def test_confirm_reject_race_executes_once() -> None:
    service = PendingConfirmationService()
    pending = await service.create(
        connection_generation=1,
        session_id="s",
        tool_name="notes.delete",
        risk=ToolRisk.HIGH,
        arguments={"note_ids": [1]},
        preview={"operation": "soft_delete"},
    )
    assert pending is not None
    entered = asyncio.Event()
    release = asyncio.Event()
    executions = 0

    async def execute(_pending) -> ToolResult:
        nonlocal executions
        executions += 1
        entered.set()
        await release.wait()
        return ToolResult("success", "ok", "notes.delete", ToolRisk.HIGH)

    confirm_task = asyncio.create_task(
        service.confirm(
            pending.confirmation_id,
            connection_generation=1,
            session_id="s",
            executor=execute,
        )
    )
    await entered.wait()
    rejected = await service.reject(
        pending.confirmation_id,
        connection_generation=1,
        session_id="s",
    )
    assert rejected.error_code == "confirmation_consumed"
    release.set()
    confirmed = await confirm_task
    assert confirmed.status == "confirmed"
    assert executions == 1


@pytest.mark.asyncio
async def test_capacity_is_bounded_and_generation_invalidation_clears_pending() -> None:
    service = PendingConfirmationService(capacity=1)
    first = await service.create(
        connection_generation=8,
        session_id="s",
        tool_name="notes.delete",
        risk=ToolRisk.HIGH,
        arguments={"note_ids": [1]},
        preview={"operation": "soft_delete"},
    )
    second = await service.create(
        connection_generation=8,
        session_id="s",
        tool_name="notes.delete",
        risk=ToolRisk.HIGH,
        arguments={"note_ids": [2]},
        preview={"operation": "soft_delete"},
    )
    assert first is not None
    assert second is None
    assert service.pending_count == 1
    assert await service.invalidate_generation(8, "disconnect") == 1
    assert service.pending_count == 0
