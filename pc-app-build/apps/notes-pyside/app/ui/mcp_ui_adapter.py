"""Qt adapter for the Gate 5.1 UI command bus."""

from __future__ import annotations

import asyncio
import time
from collections import deque

from PySide6.QtCore import QObject, Signal

from ..assistant.mcp.ui_bus import UiCommand, UiCommandKind, UiDispatchResult
from .notes_view_model import NotesViewModel


class NotesUiCommandAdapter(QObject):
    """Dispatch typed commands to NotesViewModel and expose navigation signals to QML."""

    navigationRequested = Signal(str, "QVariantMap")

    def __init__(self, view_model: NotesViewModel) -> None:
        super().__init__()
        self._view_model = view_model
        self._closed = False
        self._command_history: deque[str] = deque(maxlen=32)

    @property
    def command_history(self) -> tuple[str, ...]:
        return tuple(self._command_history)

    async def dispatch(self, command: UiCommand) -> UiDispatchResult:
        if self._closed:
            return UiDispatchResult(False, "桌面 UI 已关闭", "ui_unavailable")

        payload = dict(command.payload)
        if command.kind is UiCommandKind.OPEN_NOTE:
            note_id = int(payload["note_id"])
            self._view_model.loadAll()
            if not await self._wait_query_idle():
                return UiDispatchResult(
                    False, "等待便签列表刷新超时", "ui_refresh_timeout"
                )
            ids = self._view_model.currentNoteIds()
            if note_id not in ids:
                return UiDispatchResult(
                    False, "便签已不在活动列表中", "stale_ui_selection"
                )
            self._view_model.selectNote(ids.index(note_id))
        elif command.kind is UiCommandKind.SHOW_SEARCH:
            query = str(payload.get("query", "")).strip()
            if query:
                self._view_model.searchNotes(query)
            else:
                self._view_model.loadAll()
        elif command.kind is UiCommandKind.SHOW_NOTE_LIST:
            self._view_model.loadAll()
        elif command.kind is UiCommandKind.SHOW_TAG:
            self._view_model.loadTag(str(payload["tag"]))
        elif command.kind is UiCommandKind.SHOW_TRASH:
            self._view_model.loadDeleted()
        elif command.kind is UiCommandKind.SHOW_PINNED:
            self._view_model.loadCategory("pinned")
        else:
            return UiDispatchResult(
                False, "当前 UI 命令尚未实现", "ui_command_not_ready"
            )

        self.navigationRequested.emit(command.kind.value, payload)
        self._command_history.append(command.kind.value)
        await asyncio.sleep(0)
        return UiDispatchResult(True, "桌面 UI 已切换")

    async def close(self) -> None:
        self._closed = True

    async def _wait_query_idle(self, timeout_seconds: float = 3.0) -> bool:
        deadline = time.perf_counter() + timeout_seconds
        while time.perf_counter() < deadline:
            if not self._view_model.isBusy:
                return True
            await asyncio.sleep(0.01)
        return not self._view_model.isBusy


__all__ = ["NotesUiCommandAdapter"]
