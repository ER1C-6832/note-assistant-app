"""
Notes controller exposed to QML.

This controller connects the PC UI to the Notes API for manual note operations:
list, create, edit, soft delete, restore, pin/unpin, and fuzzy search.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.models.note import Note, NoteListModel, note_from_api
from app.services.notes_api_client import (
    NotesApiClient,
    NotesApiConnectionError,
    NotesApiError,
    NotesApiHttpError,
)


class NotesController(QObject):
    """Bridge between QML and the Notes API."""

    stateChanged = Signal()
    selectedChanged = Signal()
    statusChanged = Signal()

    _CATEGORY_TO_TAG = {
        "customer": "客户",
        "meeting": "会议",
        "todo": "待办",
        "screen": "屏幕",
        "controller": "游戏手柄",
    }

    def __init__(self) -> None:
        super().__init__()
        self._client = NotesApiClient()
        self.notes_model = NoteListModel()
        self.deleted_notes_model = NoteListModel()

        self._selected_index = -1
        self._deleted_selected_index = -1
        self._active_category = "all"
        self._search_keyword = ""
        self._status_message = "准备就绪"
        self._error_message = ""
        self._api_connected = False
        self._result_count = 0
        self._deleted_result_count = 0
        self._is_busy = False

    @Property(int, notify=selectedChanged)
    def selectedIndex(self) -> int:
        return self._selected_index

    @Property(bool, notify=selectedChanged)
    def hasSelection(self) -> bool:
        return self._selected_note() is not None

    @Property(str, notify=selectedChanged)
    def selectedTitle(self) -> str:
        note = self._selected_note()
        return note.title if note else ""

    @Property(str, notify=selectedChanged)
    def selectedContent(self) -> str:
        note = self._selected_note()
        return note.content if note else ""

    @Property(str, notify=selectedChanged)
    def selectedTagsText(self) -> str:
        note = self._selected_note()
        return note.tags_text if note else ""

    @Property(str, notify=selectedChanged)
    def selectedSourceText(self) -> str:
        note = self._selected_note()
        return note.source_text if note else ""

    @Property(str, notify=selectedChanged)
    def selectedUpdatedText(self) -> str:
        note = self._selected_note()
        return note.updated_text if note else ""

    @Property(bool, notify=selectedChanged)
    def selectedIsPinned(self) -> bool:
        note = self._selected_note()
        return bool(note and note.is_pinned)

    @Property(int, notify=selectedChanged)
    def deletedSelectedIndex(self) -> int:
        return self._deleted_selected_index

    @Property(bool, notify=selectedChanged)
    def hasDeletedSelection(self) -> bool:
        return self._deleted_selected_note() is not None

    @Property(str, notify=statusChanged)
    def statusMessage(self) -> str:
        return self._status_message

    @Property(str, notify=statusChanged)
    def errorMessage(self) -> str:
        return self._error_message

    @Property(bool, notify=statusChanged)
    def apiConnected(self) -> bool:
        return self._api_connected

    @Property(bool, notify=statusChanged)
    def isBusy(self) -> bool:
        return self._is_busy

    @Property(str, notify=stateChanged)
    def activeCategory(self) -> str:
        return self._active_category

    @Property(str, notify=stateChanged)
    def searchKeyword(self) -> str:
        return self._search_keyword

    @Property(int, notify=stateChanged)
    def resultCount(self) -> int:
        return self._result_count

    @Property(int, notify=stateChanged)
    def deletedResultCount(self) -> int:
        return self._deleted_result_count

    @Slot()
    def refresh(self) -> None:
        self._reload_current_view()

    @Slot()
    def loadAll(self) -> None:
        self._active_category = "all"
        self._search_keyword = ""
        self._set_busy(True)
        self._run_and_update(lambda: self._client.list_notes(include_deleted=False), "已加载全部便签")
        self._set_busy(False)
        self.stateChanged.emit()

    @Slot(str)
    def loadCategory(self, category_key: str) -> None:
        self._active_category = category_key
        self._search_keyword = ""
        self._set_busy(True)

        if category_key == "all":
            self._run_and_update(lambda: self._client.list_notes(include_deleted=False), "已加载全部便签")
        elif category_key == "pinned":
            try:
                notes = self._fetch_notes(include_deleted=False)
                pinned_notes = [note for note in notes if note.is_pinned]
                self._set_notes(pinned_notes, "已加载置顶便签")
            except NotesApiError as exc:
                self._handle_error(exc)
        else:
            tag = self._CATEGORY_TO_TAG.get(category_key)
            if tag:
                self._run_and_update(
                    lambda: self._client.list_notes(include_deleted=False, tag=tag),
                    f"已加载{tag}便签",
                )
            else:
                self._run_and_update(lambda: self._client.list_notes(include_deleted=False), "已加载全部便签")

        self._set_busy(False)
        self.stateChanged.emit()

    @Slot()
    def loadDeleted(self) -> None:
        self._active_category = "deleted"
        self._set_busy(True)

        try:
            notes = self._fetch_notes(include_deleted=True)
            deleted = [note for note in notes if note.is_deleted]
            self.deleted_notes_model.set_notes(deleted)
            self._deleted_result_count = len(deleted)
            self._result_count = len(deleted)
            self._deleted_selected_index = 0 if deleted else -1
            self._selected_index = -1
            self._set_connected()
            self._set_status("已加载已删除便签")
            self.selectedChanged.emit()
        except NotesApiError as exc:
            self.deleted_notes_model.set_notes([])
            self._deleted_result_count = 0
            self._result_count = 0
            self._deleted_selected_index = -1
            self._handle_error(exc)

        self._set_busy(False)
        self.stateChanged.emit()

    @Slot(str)
    def searchNotes(self, keyword: str) -> None:
        query = keyword.strip()
        self._active_category = "search"
        self._search_keyword = query

        if not query:
            self.loadAll()
            return

        self._set_busy(True)
        try:
            payload = self._client.search_notes(query=query, limit=100)
            notes = [note_from_api(item) for item in payload.get("items", [])]
            self._set_notes(notes, f"找到 {len(notes)} 条相关便签")
        except NotesApiError as exc:
            self._handle_error(exc)
            self._set_notes([], "搜索失败")

        self._set_busy(False)
        self.stateChanged.emit()

    @Slot(int)
    def selectNote(self, index: int) -> None:
        if 0 <= index < self.notes_model.count():
            self._selected_index = index
        else:
            self._selected_index = -1
        self.selectedChanged.emit()

    @Slot(int)
    def selectDeletedNote(self, index: int) -> None:
        if 0 <= index < self.deleted_notes_model.count():
            self._deleted_selected_index = index
        else:
            self._deleted_selected_index = -1
        self.selectedChanged.emit()

    @Slot(str, str, str, result=bool)
    def createNote(self, title: str, content: str, tags_text: str) -> bool:
        clean_title = title.strip()
        clean_content = content.strip()

        if not clean_title:
            self._set_error("标题不能为空")
            return False

        self._set_busy(True)
        try:
            self._client.create_note(
                title=clean_title,
                content=clean_content,
                tags=_parse_tags(tags_text),
                source="manual",
            )
            self._set_connected()
            self._set_status("便签已保存")
            self.loadAll()
            return True
        except NotesApiError as exc:
            self._handle_error(exc)
            return False
        finally:
            self._set_busy(False)

    @Slot(str, str, str, result=bool)
    def updateSelectedNote(self, title: str, content: str, tags_text: str) -> bool:
        note = self._selected_note()
        if note is None:
            self._set_error("请先选择一条便签")
            return False

        clean_title = title.strip()
        if not clean_title:
            self._set_error("标题不能为空")
            return False

        self._set_busy(True)
        try:
            self._client.update_note(
                note.id,
                title=clean_title,
                content=content.strip(),
                tags=_parse_tags(tags_text),
            )
            self._set_connected()
            self._set_status("便签已更新")
            self._reload_current_view()
            return True
        except NotesApiError as exc:
            self._handle_error(exc)
            return False
        finally:
            self._set_busy(False)

    @Slot(result=bool)
    def deleteSelectedNote(self) -> bool:
        note = self._selected_note()
        if note is None:
            self._set_error("请先选择一条便签")
            return False
        return self._soft_delete_ids([note.id])

    @Slot("QVariantList", result=bool)
    def bulkDeleteNotesByIds(self, note_ids) -> bool:
        ids = _normalize_ids(note_ids)
        if not ids:
            self._set_error("请选择便签")
            return False
        return self._soft_delete_ids(ids)

    @Slot("QVariantList", result=bool)
    def bulkPinNotesByIds(self, note_ids) -> bool:
        ids = _normalize_ids(note_ids)
        if not ids:
            self._set_error("请选择便签")
            return False
        self._set_busy(True)
        try:
            for note_id in ids:
                self._client.update_note(note_id, is_pinned=True)
            self._set_connected()
            self._set_status(f"已置顶 {len(ids)} 条便签")
            self._reload_current_view()
            return True
        except NotesApiError as exc:
            self._handle_error(exc)
            return False
        finally:
            self._set_busy(False)

    @Slot(result=bool)
    def toggleSelectedPin(self) -> bool:
        note = self._selected_note()
        if note is None:
            self._set_error("请先选择一条便签")
            return False

        self._set_busy(True)
        try:
            self._client.update_note(note.id, is_pinned=not note.is_pinned)
            self._set_connected()
            self._set_status("已置顶" if not note.is_pinned else "已取消置顶")
            self.loadCategory(self._active_category or "all")
            return True
        except NotesApiError as exc:
            self._handle_error(exc)
            return False
        finally:
            self._set_busy(False)

    @Slot(result=bool)
    def restoreSelectedDeletedNote(self) -> bool:
        note = self._deleted_selected_note()
        if note is None:
            self._set_error("请先选择一条已删除便签")
            return False

        return self.bulkRestoreDeletedNotesByIds([note.id])

    @Slot(int, result=bool)
    def restoreDeletedNoteAt(self, index: int) -> bool:
        self.selectDeletedNote(index)
        return self.restoreSelectedDeletedNote()


    @Slot("QVariantList", result=bool)
    def bulkRestoreDeletedNotesByIds(self, note_ids) -> bool:
        ids = _normalize_ids(note_ids)
        if not ids:
            self._set_error("请选择已删除便签")
            return False
        self._set_busy(True)
        try:
            for note_id in ids:
                self._client.restore_note(note_id)
            self._set_connected()
            self._set_status(f"已还原 {len(ids)} 条便签")
            self.loadDeleted()
            return True
        except NotesApiError as exc:
            self._handle_error(exc)
            return False
        finally:
            self._set_busy(False)

    @Slot(int, result=bool)
    def hardDeleteDeletedNoteAt(self, index: int) -> bool:
        note = self.deleted_notes_model.get_note(index)
        if note is None:
            self._set_error("请先选择一条已删除便签")
            return False
        return self.bulkHardDeleteDeletedNotesByIds([note.id])

    @Slot("QVariantList", result=bool)
    def bulkHardDeleteDeletedNotesByIds(self, note_ids) -> bool:
        ids = _normalize_ids(note_ids)
        if not ids:
            self._set_error("请选择已删除便签")
            return False
        self._set_busy(True)
        try:
            for note_id in ids:
                self._client.hard_delete_note(note_id)
            self._set_connected()
            self._set_status(f"已彻底删除 {len(ids)} 条便签")
            self.loadDeleted()
            return True
        except NotesApiError as exc:
            self._handle_error(exc)
            return False
        finally:
            self._set_busy(False)

    def _soft_delete_ids(self, ids: list[int]) -> bool:
        self._set_busy(True)
        try:
            for note_id in ids:
                self._client.delete_note(note_id)
            self._set_connected()
            self._set_status(f"已删除 {len(ids)} 条便签")
            self._reload_current_view()
            return True
        except NotesApiError as exc:
            self._handle_error(exc)
            return False
        finally:
            self._set_busy(False)

    def _reload_current_view(self) -> None:
        if self._active_category == "search" and self._search_keyword:
            self.searchNotes(self._search_keyword)
        elif self._active_category == "deleted":
            self.loadDeleted()
        else:
            self.loadCategory(self._active_category or "all")

    @Slot(result=bool)
    def testConnection(self) -> bool:
        self._set_busy(True)
        try:
            self._client.health()
            self._set_connected()
            self._set_status("Notes API 已连接")
            return True
        except NotesApiError as exc:
            self._handle_error(exc)
            return False
        finally:
            self._set_busy(False)

    def _fetch_notes(self, *, include_deleted: bool) -> list[Note]:
        payload = self._client.list_notes(include_deleted=include_deleted, limit=200)
        self._set_connected()
        return [note_from_api(item) for item in payload]

    def _run_and_update(self, fetcher, success_message: str) -> None:
        try:
            payload = fetcher()
            notes = [note_from_api(item) for item in payload]
            self._set_notes(notes, success_message)
        except NotesApiError as exc:
            self._handle_error(exc)
            self._set_notes([], "加载失败")

    def _set_notes(self, notes: list[Note], status_message: str) -> None:
        self.notes_model.set_notes(notes)
        self._result_count = len(notes)
        self._selected_index = 0 if notes else -1
        self._deleted_selected_index = -1
        self._set_connected()
        self._set_status(status_message)
        self.selectedChanged.emit()

    def _selected_note(self) -> Note | None:
        return self.notes_model.get_note(self._selected_index)

    def _deleted_selected_note(self) -> Note | None:
        return self.deleted_notes_model.get_note(self._deleted_selected_index)

    def _set_busy(self, value: bool) -> None:
        if self._is_busy != value:
            self._is_busy = value
            self.statusChanged.emit()

    def _set_connected(self) -> None:
        if not self._api_connected:
            self._api_connected = True
            self.statusChanged.emit()

    def _set_status(self, message: str) -> None:
        self._status_message = message
        self._error_message = ""
        self.statusChanged.emit()

    def _set_error(self, message: str, *, mark_offline: bool = False) -> None:
        self._error_message = message
        self._status_message = "操作失败"
        if mark_offline:
            self._api_connected = False
        self.statusChanged.emit()

    def _handle_error(self, exc: NotesApiError) -> None:
        if isinstance(exc, NotesApiConnectionError):
            self._set_error(str(exc), mark_offline=True)
        elif isinstance(exc, NotesApiHttpError):
            self._api_connected = True
            self._set_error(str(exc), mark_offline=False)
        else:
            self._set_error(str(exc), mark_offline=False)


def _parse_tags(tags_text: str) -> list[str]:
    separators = [",", "，", "、", "·", "|", ";", "；", " "]
    normalized = tags_text

    for sep in separators:
        normalized = normalized.replace(sep, ",")

    return [tag.strip() for tag in normalized.split(",") if tag.strip()]


def _normalize_ids(note_ids) -> list[int]:
    ids: list[int] = []
    for value in note_ids:
        try:
            ids.append(int(value))
        except (TypeError, ValueError):
            continue
    return ids
