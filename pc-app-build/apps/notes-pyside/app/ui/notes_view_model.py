"""Asynchronous Qt view model for the single-process notes application."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, TypeVar

from PySide6.QtCore import QObject, Property, Signal, Slot

from ..notes import (
    CreateNoteCommand,
    HardDeleteCommand,
    Note,
    NoteCommandService,
    NoteQueryService,
    NoteServiceError,
    NoteSource,
    RestoreCommand,
    SetPinnedCommand,
    SoftDeleteCommand,
    TagCatalog,
    TagCatalogError,
    TagInUseError,
    TagValidationError,
    UpdateNoteCommand,
)
from .note_list_model import NoteListModel

T = TypeVar("T")
_TAG_SPLITTER = re.compile(r"[\s,，、#]+")


class NotesViewModel(QObject):
    """Single Qt-facing owner of note-list UI state.

    The model mirrors the Android architecture: UI observes one ViewModel, while all
    persistence work crosses the application-service boundary. Query generations
    prevent stale async results from replacing the latest requested view.
    """

    stateChanged = Signal()
    selectedChanged = Signal()
    statusChanged = Signal()
    tagsChanged = Signal()

    noteCreated = Signal(int)
    noteUpdated = Signal(int)
    notesSoftDeleted = Signal("QVariantList")
    notesRestored = Signal("QVariantList")
    notesHardDeleted = Signal("QVariantList")
    pinStateChanged = Signal("QVariantList", bool)
    tagAdded = Signal(str)
    tagDeleted = Signal(str)
    operationFailed = Signal(str, str)

    def __init__(
        self,
        command_service: NoteCommandService,
        query_service: NoteQueryService,
        tag_catalog: TagCatalog,
        notes_model: NoteListModel,
        deleted_notes_model: NoteListModel,
    ) -> None:
        super().__init__()
        self._command_service = command_service
        self._query_service = query_service
        self._tag_catalog = tag_catalog
        self._notes_model = notes_model
        self._deleted_notes_model = deleted_notes_model

        self._active_category = "all"
        self._search_keyword = ""
        self._status_message = "便签服务已就绪"
        self._error_message = ""
        self._query_busy = False
        self._mutation_busy = False
        self._query_generation = 0
        self._query_task: asyncio.Task[None] | None = None
        self._mutation_task: asyncio.Task[None] | None = None
        self._selected_note_id: int | None = None
        self._deleted_selected_note_id: int | None = None
        self._known_used_tags: set[str] = set()

    @Property(int, notify=selectedChanged)
    def selectedIndex(self) -> int:
        return self._notes_model.index_of_id(self._selected_note_id)

    @Property(bool, notify=selectedChanged)
    def hasSelection(self) -> bool:
        return self._selected_note() is not None

    @Property(str, notify=selectedChanged)
    def selectedTitle(self) -> str:
        note = self._selected_note()
        return note.title if note is not None else ""

    @Property(str, notify=selectedChanged)
    def selectedContent(self) -> str:
        note = self._selected_note()
        return note.content if note is not None else ""

    @Property(str, notify=selectedChanged)
    def selectedTagsText(self) -> str:
        note = self._selected_note()
        return "、".join(note.tags) if note is not None else ""

    @Property(str, notify=selectedChanged)
    def selectedSourceText(self) -> str:
        note = self._selected_note()
        if note is None:
            return ""
        return {
            NoteSource.MANUAL: "手动",
            NoteSource.VOICE_PC: "PC 语音",
            NoteSource.VOICE_ANDROID: "Android 语音",
            NoteSource.IMPORTED: "导入",
        }.get(note.source, str(note.source))

    @Property(str, notify=selectedChanged)
    def selectedUpdatedText(self) -> str:
        note = self._selected_note()
        return note.updated_at.astimezone().strftime("%Y-%m-%d %H:%M") if note else ""

    @Property(bool, notify=selectedChanged)
    def selectedIsPinned(self) -> bool:
        note = self._selected_note()
        return bool(note and note.is_pinned)

    @Property(int, notify=selectedChanged)
    def deletedSelectedIndex(self) -> int:
        return self._deleted_notes_model.index_of_id(self._deleted_selected_note_id)

    @Property(str, notify=stateChanged)
    def activeCategory(self) -> str:
        return self._active_category

    @Property(str, notify=stateChanged)
    def searchKeyword(self) -> str:
        return self._search_keyword

    @Property(int, notify=stateChanged)
    def resultCount(self) -> int:
        return self._notes_model.rowCount()

    @Property(int, notify=stateChanged)
    def deletedResultCount(self) -> int:
        return self._deleted_notes_model.rowCount()

    @Property(str, notify=statusChanged)
    def statusMessage(self) -> str:
        return self._status_message

    @Property(str, notify=statusChanged)
    def errorMessage(self) -> str:
        return self._error_message

    @Property(bool, notify=statusChanged)
    def isBusy(self) -> bool:
        return self._query_busy or self._mutation_busy

    @Property(bool, notify=statusChanged)
    def mutationBusy(self) -> bool:
        return self._mutation_busy

    @Property("QVariantList", notify=tagsChanged)
    def tagItems(self) -> list[dict[str, object]]:
        return [
            {
                "name": item.name,
                "deletable": item.deletable,
                "protected": item.protected,
                "inUse": item.in_use,
            }
            for item in self._tag_catalog.items(used_tags=self._known_used_tags)
        ]

    @Slot()
    def loadAll(self) -> None:
        self._submit_query("all", "", self._query_service.list_all, "全部便签")

    @Slot(str)
    def loadCategory(self, category_key: str) -> None:
        category = str(category_key).strip().lower() or "all"
        if category == "pinned":
            self._submit_query("pinned", "", self._query_service.list_pinned, "置顶便签")
        elif category == "todo":
            self._submit_query(
                "todo",
                "",
                lambda: self._query_service.list_by_tag("待办"),
                "待办便签",
            )
        elif category == "deleted":
            self.loadDeleted()
        else:
            self.loadAll()

    @Slot(str)
    def loadTag(self, tag: str) -> None:
        clean_tag = str(tag).strip()
        if not clean_tag:
            self.loadAll()
            return
        self._submit_query(
            f"tag:{clean_tag}",
            "",
            lambda: self._query_service.list_by_tag(clean_tag),
            f"标签：{clean_tag}",
        )

    @Slot()
    def loadDeleted(self) -> None:
        self._submit_query(
            "deleted",
            "",
            self._query_service.list_deleted,
            "已删除便签",
            deleted=True,
        )

    @Slot(str)
    def searchNotes(self, keyword: str) -> None:
        query = str(keyword).strip()
        if not query:
            self.loadAll()
            return
        self._submit_query(
            "search",
            query,
            lambda: self._query_service.search(query),
            f"搜索：{query}",
        )

    @Slot()
    def refreshCurrentView(self) -> None:
        category = self._active_category
        if category == "pinned":
            self.loadCategory("pinned")
        elif category == "todo":
            self.loadCategory("todo")
        elif category == "deleted":
            self.loadDeleted()
        elif category == "search":
            self.searchNotes(self._search_keyword)
        elif category.startswith("tag:"):
            self.loadTag(category.partition(":")[2])
        else:
            self.loadAll()

    @Slot(int)
    def selectNote(self, index: int) -> None:
        note = self._notes_model.note_at(index)
        new_id = note.id if note is not None else None
        if new_id != self._selected_note_id:
            self._selected_note_id = new_id
            self.selectedChanged.emit()

    @Slot(int)
    def selectDeletedNote(self, index: int) -> None:
        note = self._deleted_notes_model.note_at(index)
        new_id = note.id if note is not None else None
        if new_id != self._deleted_selected_note_id:
            self._deleted_selected_note_id = new_id
            self.selectedChanged.emit()

    @Slot(result="QVariantList")
    def currentNoteIds(self) -> list[int]:
        return self._notes_model.note_ids()

    @Slot(result="QVariantList")
    def currentDeletedNoteIds(self) -> list[int]:
        return self._deleted_notes_model.note_ids()

    @Slot(str, str, str, bool)
    def requestCreateNote(self, title: str, content: str, tags_text: str, is_pinned: bool) -> None:
        try:
            command = CreateNoteCommand(
                title=title,
                content=content,
                tags=_parse_tags(tags_text),
                is_pinned=is_pinned,
                source=NoteSource.MANUAL,
            )
        except (TypeError, ValueError) as exc:
            self._fail("create", str(exc))
            return

        async def execute() -> Note:
            return await self._command_service.create(command)

        def succeeded(note: Note) -> None:
            self._observe_tags(note.tags)
            self.noteCreated.emit(note.id)

        self._submit_mutation("create", execute, succeeded, "便签已创建")

    @Slot(str, str, str)
    def requestUpdateSelectedNote(self, title: str, content: str, tags_text: str) -> None:
        selected = self._selected_note()
        if selected is None:
            self._fail("update", "请先选择便签")
            return
        try:
            command = UpdateNoteCommand(
                note_id=selected.id,
                title=title,
                content=content,
                tags=_parse_tags(tags_text),
            )
        except (TypeError, ValueError) as exc:
            self._fail("update", str(exc))
            return

        async def execute() -> Note:
            return await self._command_service.update(command)

        def succeeded(note: Note) -> None:
            self._selected_note_id = note.id
            self._observe_tags(note.tags)
            self.noteUpdated.emit(note.id)

        self._submit_mutation("update", execute, succeeded, "便签已更新")

    @Slot()
    def requestDeleteSelectedNote(self) -> None:
        selected = self._selected_note()
        if selected is None:
            self._fail("delete", "请先选择便签")
            return
        self._request_soft_delete((selected.id,), "delete")

    @Slot()
    def requestToggleSelectedPin(self) -> None:
        selected = self._selected_note()
        if selected is None:
            self._fail("toggle_pin", "请先选择便签")
            return
        self._request_pin((selected.id,), not selected.is_pinned, "toggle_pin")

    @Slot("QVariantList")
    def requestBulkDelete(self, note_ids) -> None:
        self._request_soft_delete(_coerce_ids(note_ids), "bulk_delete")

    @Slot("QVariantList")
    def requestBulkPin(self, note_ids) -> None:
        self._request_pin(_coerce_ids(note_ids), True, "bulk_pin")

    @Slot("QVariantList")
    def requestBulkUnpin(self, note_ids) -> None:
        self._request_pin(_coerce_ids(note_ids), False, "bulk_unpin")

    @Slot(int)
    def requestRestoreDeletedAt(self, index: int) -> None:
        note = self._deleted_notes_model.note_at(index)
        if note is None:
            self._fail("restore", "请选择要恢复的便签")
            return
        self._request_restore((note.id,), "restore")

    @Slot("QVariantList")
    def requestBulkRestoreDeleted(self, note_ids) -> None:
        self._request_restore(_coerce_ids(note_ids), "bulk_restore")

    @Slot("QVariantList")
    def requestBulkHardDeleteDeleted(self, note_ids) -> None:
        ids = _coerce_ids(note_ids)
        try:
            command = HardDeleteCommand(ids)
        except (TypeError, ValueError) as exc:
            self._fail("bulk_hard_delete", str(exc))
            return

        async def execute() -> int:
            return await self._command_service.hard_delete(command)

        def succeeded(_count: int) -> None:
            self.notesHardDeleted.emit(list(command.note_ids))

        self._submit_mutation(
            "bulk_hard_delete",
            execute,
            succeeded,
            "便签已彻底删除",
        )

    @Slot(str)
    def requestAddCustomTag(self, tag: str) -> None:
        clean_tag = str(tag).strip()
        if not clean_tag:
            self._fail("add_tag", "标签不能为空")
            return

        async def execute() -> bool:
            return await asyncio.to_thread(self._tag_catalog.add, clean_tag)

        def succeeded(added: bool) -> None:
            if added:
                self.tagsChanged.emit()
                self.tagAdded.emit(clean_tag)

        self._submit_mutation("add_tag", execute, succeeded, "标签已添加")

    @Slot(str)
    def requestDeleteTag(self, tag: str) -> None:
        clean_tag = str(tag).strip()
        if not clean_tag:
            self._fail("delete_tag", "标签不能为空")
            return

        async def execute() -> bool:
            active, deleted = await asyncio.gather(
                self._query_service.list_all(),
                self._query_service.list_deleted(),
            )
            used_tags = {value for note in (*active, *deleted) for value in note.tags}
            return await asyncio.to_thread(
                self._tag_catalog.delete,
                clean_tag,
                used_tags=used_tags,
            )

        def succeeded(deleted: bool) -> None:
            if deleted:
                self.tagsChanged.emit()
                self.tagDeleted.emit(clean_tag)

        self._submit_mutation("delete_tag", execute, succeeded, "标签已删除")

    async def close(self) -> None:
        tasks = [task for task in (self._query_task, self._mutation_task) if task is not None]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _submit_query(
        self,
        category: str,
        keyword: str,
        query: Callable[[], Awaitable[tuple[Note, ...]]],
        label: str,
        *,
        deleted: bool = False,
    ) -> None:
        self._query_generation += 1
        generation = self._query_generation
        if self._query_task is not None and not self._query_task.done():
            self._query_task.cancel()

        self._active_category = category
        self._search_keyword = keyword
        self._error_message = ""
        self._set_query_busy(True)
        self.stateChanged.emit()

        async def run() -> None:
            try:
                notes = await query()
            except asyncio.CancelledError:
                return
            except Exception as exc:
                if generation == self._query_generation:
                    self._fail("query", _error_message(exc))
                return

            if generation != self._query_generation:
                return
            if deleted:
                self._replace_deleted_notes(notes)
            else:
                self._replace_active_notes(notes)
            self._observe_tags(tag for note in notes for tag in note.tags)
            self._status_message = f"{label}：{len(notes)} 条"
            self._error_message = ""
            self.stateChanged.emit()
            self.statusChanged.emit()
            await self._refresh_known_used_tags()

        async def guarded() -> None:
            try:
                await run()
            finally:
                if generation == self._query_generation:
                    self._set_query_busy(False)

        self._query_task = self._create_task("query", guarded())
        if self._query_task is None:
            self._set_query_busy(False)

    def _submit_mutation(
        self,
        operation: str,
        execute: Callable[[], Awaitable[T]],
        succeeded: Callable[[T], None],
        success_message: str,
    ) -> None:
        if self._mutation_busy or (
            self._mutation_task is not None and not self._mutation_task.done()
        ):
            self._fail(operation, "操作正在进行，请稍候")
            return

        async def run() -> None:
            self._set_mutation_busy(True)
            try:
                result = await execute()
                self._status_message = success_message
                self._error_message = ""
                self.statusChanged.emit()
                succeeded(result)
                await self._refresh_known_used_tags()
                self.refreshCurrentView()
            except asyncio.CancelledError:
                return
            except Exception as exc:
                self._fail(operation, _error_message(exc))
            finally:
                self._set_mutation_busy(False)

        self._mutation_task = self._create_task(operation, run())

    def _request_soft_delete(self, note_ids: tuple[int, ...], operation: str) -> None:
        try:
            command = SoftDeleteCommand(note_ids)
        except (TypeError, ValueError) as exc:
            self._fail(operation, str(exc))
            return

        async def execute() -> int:
            return await self._command_service.soft_delete(command)

        def succeeded(_count: int) -> None:
            self.notesSoftDeleted.emit(list(command.note_ids))

        self._submit_mutation(operation, execute, succeeded, "便签已移入已删除")

    def _request_restore(self, note_ids: tuple[int, ...], operation: str) -> None:
        try:
            command = RestoreCommand(note_ids)
        except (TypeError, ValueError) as exc:
            self._fail(operation, str(exc))
            return

        async def execute() -> int:
            return await self._command_service.restore(command)

        def succeeded(_count: int) -> None:
            self.notesRestored.emit(list(command.note_ids))

        self._submit_mutation(operation, execute, succeeded, "便签已恢复")

    def _request_pin(self, note_ids: tuple[int, ...], pinned: bool, operation: str) -> None:
        try:
            command = SetPinnedCommand(note_ids, pinned)
        except (TypeError, ValueError) as exc:
            self._fail(operation, str(exc))
            return

        async def execute() -> tuple[Note, ...]:
            return await self._command_service.set_pinned(command)

        def succeeded(_notes: tuple[Note, ...]) -> None:
            self.pinStateChanged.emit(list(command.note_ids), command.is_pinned)

        message = "便签已置顶" if pinned else "便签已取消置顶"
        self._submit_mutation(operation, execute, succeeded, message)

    def _replace_active_notes(self, notes: tuple[Note, ...]) -> None:
        previous = self._selected_note_id
        self._notes_model.replace_notes(notes)
        if self._notes_model.note_by_id(previous) is not None:
            self._selected_note_id = previous
        else:
            self._selected_note_id = self._notes_model.first_note_id()
        self.selectedChanged.emit()

    def _replace_deleted_notes(self, notes: tuple[Note, ...]) -> None:
        previous = self._deleted_selected_note_id
        self._deleted_notes_model.replace_notes(notes)
        self._deleted_selected_note_id = (
            previous
            if self._deleted_notes_model.note_by_id(previous) is not None
            else self._deleted_notes_model.first_note_id()
        )
        self.selectedChanged.emit()

    def _selected_note(self) -> Note | None:
        return self._notes_model.note_by_id(self._selected_note_id)

    def _observe_tags(self, tags: Iterable[str]) -> None:
        normalized = tuple(str(tag).strip() for tag in tags if str(tag).strip())
        if not normalized:
            return
        before = set(self._tag_catalog.custom_tags)
        self._known_used_tags.update(normalized)
        additions = self._tag_catalog.observe(normalized)
        if additions or before != set(self._tag_catalog.custom_tags):
            self.tagsChanged.emit()
        else:
            # inUse/deletable can still change when a known tag appears in a note.
            self.tagsChanged.emit()

    async def _refresh_known_used_tags(self) -> None:
        active, deleted = await asyncio.gather(
            self._query_service.list_all(),
            self._query_service.list_deleted(),
        )
        used = {tag for note in (*active, *deleted) for tag in note.tags}
        previous = self._known_used_tags
        self._known_used_tags = used
        additions = await asyncio.to_thread(self._tag_catalog.observe, used)
        if used != previous or additions:
            self.tagsChanged.emit()

    def _set_query_busy(self, value: bool) -> None:
        if self._query_busy == value:
            return
        self._query_busy = value
        self.statusChanged.emit()

    def _set_mutation_busy(self, value: bool) -> None:
        if self._mutation_busy == value:
            return
        self._mutation_busy = value
        self.statusChanged.emit()

    def _fail(self, operation: str, message: str) -> None:
        self._status_message = "操作失败"
        self._error_message = message
        self.statusChanged.emit()
        self.operationFailed.emit(operation, message)

    def _create_task(self, operation: str, coroutine: Awaitable[None]) -> asyncio.Task[None] | None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            coroutine.close()  # type: ignore[attr-defined]
            self._fail(operation, "异步事件循环尚未启动")
            return None
        return loop.create_task(coroutine)


def _parse_tags(value: str) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for tag in _TAG_SPLITTER.split(str(value).strip()):
        clean_tag = tag.strip()
        if not clean_tag or clean_tag in seen:
            continue
        seen.add(clean_tag)
        result.append(clean_tag)
    return tuple(result)


def _coerce_ids(values: Any) -> tuple[int, ...]:
    if values is None:
        return ()
    try:
        return tuple(int(value) for value in values)
    except (TypeError, ValueError):
        return ()


def _error_message(exc: Exception) -> str:
    if isinstance(exc, TagInUseError):
        return f"标签“{exc.tag}”仍被便签引用，暂时不能删除"
    if isinstance(exc, TagValidationError):
        return "该标签受保护或不是可删除的自定义标签"
    if isinstance(exc, (NoteServiceError, TagCatalogError, TypeError, ValueError)):
        return str(exc)
    return "便签操作失败，请查看日志后重试"
