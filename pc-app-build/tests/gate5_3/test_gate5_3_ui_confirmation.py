from __future__ import annotations

import asyncio

import pytest

from app.assistant.mcp import ToolResult, ToolRisk, UiCommand, UiCommandKind
from app.ui.mcp_ui_adapter import NotesUiCommandAdapter


class FakeViewModel:
    isBusy = False


class FakeActions:
    def __init__(self) -> None:
        self.confirmed: list[str] = []
        self.rejected: list[str] = []

    async def confirm_local(self, confirmation_id: str) -> ToolResult:
        self.confirmed.append(confirmation_id)
        return ToolResult("success", "已确认", "assistant.confirm", ToolRisk.HIGH_GATEWAY)

    async def reject_local(self, confirmation_id: str) -> ToolResult:
        self.rejected.append(confirmation_id)
        return ToolResult("success", "已拒绝", "assistant.reject", ToolRisk.LOW)


@pytest.mark.asyncio
async def test_ui_show_and_local_actions_share_bound_executor() -> None:
    adapter = NotesUiCommandAdapter(FakeViewModel())  # type: ignore[arg-type]
    actions = FakeActions()
    adapter.bind_confirmation_actions(actions)
    navigations = []
    finishes = []
    adapter.navigationRequested.connect(
        lambda command, payload: navigations.append((command, dict(payload)))
    )
    adapter.confirmationActionFinished.connect(
        lambda confirmation_id, status, message: finishes.append((confirmation_id, status, message))
    )

    shown = await adapter.dispatch(
        UiCommand(
            UiCommandKind.SHOW_CONFIRMATION,
            {
                "confirmation_id": "pending-1",
                "tool_name": "notes.delete",
                "preview": {"operation": "soft_delete", "note_count": 1},
                "affected_note_ids": [5],
            },
        )
    )
    assert shown.accepted is True
    assert navigations[0][0] == "show_confirmation"

    adapter.confirmPending("pending-1")
    for _ in range(100):
        if finishes:
            break
        await asyncio.sleep(0.01)
    assert actions.confirmed == ["pending-1"]
    assert finishes == [("pending-1", "success", "已确认")]
    await adapter.close()
