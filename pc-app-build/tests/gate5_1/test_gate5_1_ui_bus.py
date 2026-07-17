from __future__ import annotations

import asyncio

import pytest

from app.assistant.mcp import UiCommand, UiCommandBus, UiCommandKind, UiDispatchResult


class Adapter:
    def __init__(self, gate: asyncio.Event | None = None) -> None:
        self.gate = gate
        self.closed = False
        self.calls = 0

    async def dispatch(self, command):
        self.calls += 1
        if self.gate is not None:
            await self.gate.wait()
        return UiDispatchResult(True, command.kind.value)

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_ui_bus_drops_result_from_stale_generation() -> None:
    gate = asyncio.Event()
    first = Adapter(gate)
    second = Adapter()
    bus = UiCommandBus()
    bus.bind(first)

    task = asyncio.create_task(bus.dispatch(UiCommand(UiCommandKind.SHOW_NOTE_LIST)))
    await asyncio.sleep(0)
    bus.bind(second)
    gate.set()
    result = await task

    assert result.accepted is False
    assert result.error_code == "stale_ui_generation"
    assert bus.active_dispatch_count == 0


@pytest.mark.asyncio
async def test_ui_bus_close_rejects_new_commands_and_closes_adapter() -> None:
    adapter = Adapter()
    bus = UiCommandBus()
    bus.bind(adapter)
    await bus.close()

    result = await bus.dispatch(UiCommand(UiCommandKind.SHOW_NOTE_LIST))
    assert result.accepted is False
    assert result.error_code == "ui_unavailable"
    assert adapter.closed is True
    assert bus.active_dispatch_count == 0
