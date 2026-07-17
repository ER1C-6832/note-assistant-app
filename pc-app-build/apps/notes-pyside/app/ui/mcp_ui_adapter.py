"""Qt adapter for MCP navigation, refresh, and confirmation commands."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Protocol

from PySide6.QtCore import QObject, Signal, Slot

from ..assistant.mcp.contracts import ToolResult
from ..assistant.mcp.ui_bus import UiCommand, UiCommandKind, UiDispatchResult
from .notes_view_model import NotesViewModel


class ConfirmationActions(Protocol):
    async def confirm_local(self, confirmation_id: str) -> ToolResult: ...

    async def reject_local(self, confirmation_id: str) -> ToolResult: ...


class NotesUiCommandAdapter(QObject):
    """Dispatch typed commands to NotesViewModel and expose safe signals to QML."""

    navigationRequested = Signal(str, "QVariantMap")
    confirmationActionFinished = Signal(str, str, str)

    def __init__(self, view_model: NotesViewModel) -> None:
        super().__init__()
        self._view_model = view_model
        self._confirmation_actions: ConfirmationActions | None = None
        self._closed = False
        self._command_history: deque[str] = deque(maxlen=32)
        self._confirmation_tasks: set[asyncio.Task[None]] = set()

    @property
    def command_history(self) -> tuple[str, ...]:
        return tuple(self._command_history)

    def bind_confirmation_actions(self, actions: ConfirmationActions) -> None:
        if self._closed:
            raise RuntimeError("UI command adapter is closed")
        self._confirmation_actions = actions

    async def dispatch(self, command: UiCommand) -> UiDispatchResult:
        if self._closed:
            return UiDispatchResult(False, "桌面 UI 已关闭", "ui_unavailable")

        payload = dict(command.payload)
        if command.kind is UiCommandKind.OPEN_NOTE:
            note_id = int(payload["note_id"])
            self._view_model.loadAll()
            if not await self._wait_query_idle():
                return UiDispatchResult(False, "等待便签列表刷新超时", "ui_refresh_timeout")
            ids = self._view_model.currentNoteIds()
            if note_id not in ids:
                return UiDispatchResult(False, "便签已不在活动列表中", "stale_ui_selection")
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
        elif command.kind is UiCommandKind.SHOW_TODOS:
            self._view_model.loadCategory("todo")
        elif command.kind is UiCommandKind.SHOW_CONFIRMATION:
            if self._confirmation_actions is None:
                return UiDispatchResult(
                    False, "确认操作桥接尚未就绪", "confirmation_ui_unavailable"
                )
        elif command.kind is UiCommandKind.REFRESH_CURRENT:
            self._view_model.refreshCurrentView()
            self._view_model.tagsChanged.emit()
        elif command.kind is UiCommandKind.REFRESH_TAGS:
            self._view_model.tagsChanged.emit()
        else:
            return UiDispatchResult(False, "当前 UI 命令尚未实现", "ui_command_not_ready")

        if command.kind not in {
            UiCommandKind.REFRESH_CURRENT,
            UiCommandKind.REFRESH_TAGS,
        }:
            self.navigationRequested.emit(command.kind.value, payload)
        self._command_history.append(command.kind.value)
        await asyncio.sleep(0)
        return UiDispatchResult(True, "桌面 UI 已切换")

    @Slot(str)
    def confirmPending(self, confirmation_id: str) -> None:
        self._submit_confirmation_action("confirm", confirmation_id)

    @Slot(str)
    def rejectPending(self, confirmation_id: str) -> None:
        self._submit_confirmation_action("reject", confirmation_id)

    async def close(self) -> None:
        self._closed = True
        self._confirmation_actions = None
        tasks = tuple(self._confirmation_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._confirmation_tasks.clear()

    async def _wait_query_idle(self, timeout_seconds: float = 3.0) -> bool:
        deadline = time.perf_counter() + timeout_seconds
        while time.perf_counter() < deadline:
            if not self._view_model.isBusy:
                return True
            await asyncio.sleep(0.01)
        return not self._view_model.isBusy

    def _submit_confirmation_action(self, action: str, confirmation_id: str) -> None:
        clean_id = str(confirmation_id).strip()
        actions = self._confirmation_actions
        if self._closed or actions is None or not clean_id:
            self.confirmationActionFinished.emit(clean_id, "blocked", "确认操作当前不可用")
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self.confirmationActionFinished.emit(clean_id, "blocked", "异步事件循环尚未启动")
            return

        async def run() -> None:
            try:
                result = (
                    await actions.confirm_local(clean_id)
                    if action == "confirm"
                    else await actions.reject_local(clean_id)
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                self.confirmationActionFinished.emit(clean_id, "failed", "确认操作执行失败")
                return
            self.confirmationActionFinished.emit(clean_id, result.status, result.message)

        task = loop.create_task(run(), name=f"assistant-local-{action}-{clean_id[:8]}")
        self._confirmation_tasks.add(task)
        task.add_done_callback(self._confirmation_tasks.discard)


__all__ = ["ConfirmationActions", "NotesUiCommandAdapter"]
