from __future__ import annotations

import pytest

from app.assistant.mcp import UiCommand, UiCommandKind
from app.ui.mcp_ui_adapter import NotesUiCommandAdapter


class FakeViewModel:
    isBusy = False

    def __init__(self) -> None:
        self.load_all_count = 0

    def loadAll(self) -> None:
        self.load_all_count += 1


@pytest.mark.asyncio
async def test_ui_adapter_records_only_successful_command_kinds() -> None:
    view_model = FakeViewModel()
    adapter = NotesUiCommandAdapter(view_model)  # type: ignore[arg-type]

    result = await adapter.dispatch(UiCommand(UiCommandKind.SHOW_NOTE_LIST))

    assert result.accepted is True
    assert view_model.load_all_count == 1
    assert adapter.command_history == ("show_note_list",)

    await adapter.close()
    rejected = await adapter.dispatch(UiCommand(UiCommandKind.SHOW_NOTE_LIST))
    assert rejected.accepted is False
    assert adapter.command_history == ("show_note_list",)
