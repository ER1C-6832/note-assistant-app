"""
Notes controller exposed to QML.

Phase 4 connects the PC UI to the Notes API for manual CRUD and fuzzy search.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.models.note import Note, NoteListModel, note_from_api
from app.services.notes_api_client import NotesApiClient, NotesApiError


class NotesController(QObject):
    """Bridge between QML and the Notes API."""

    stateChanged = Signal()
    selectedChanged = Signal()
    statusChanged = Signal()

    _CATEGORY_TO_TAG = {
        "customer": "客户",
        "meeting": "会议",
        "todo": "待办",
        "tech": "技术",
    }

    def __init__(self) -> None:
        super().__init__()
        self._client = NotesApiClient()
        self.notes_model = NoteListModel()
        self.deleted_notes_model = NoteListModel()

        self._current_notes: list[Note] = []
        self._all_notes_cache: list[Note] = []
        self._selected_index = -1
        self._active_category = "all"
        self._search_keyword = ""
        self._status_message = "准备就绪"
        self._error_message = ""
        self._api_connected = False
        self._result_count = 0

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

    @Property(str, notify=statusChanged)
    def statusMessage(self) -> str:
        return self._status_message

    @Property(str, notify=statusChanged)
    def errorMessage(self) -> str:
        return self._error_message

    @Property(bool, notify=statusChanged)
    def apiConnected(self) -> bool:
        return self._api_connected

    @Property(str, notify=stateChanged)
    def activeCategory(self) -> str:
        return self._active_category

    @Property(str, notify=stateChanged)
    def searchKeyword(self) -> str:
        return self._search_keyword

    @Property(int, notify=stateChanged)
    def resultCount(self) -> int:
        return self._result_count

    @Slot()
    def refresh(self) -> None:
        self.loadAll()

    @Slot()
    def loadAll(self) -> None:
        self._active_category = "all"
        self._search_keyword = ""
        self._run_and_update(lambda: self._client.list_notes(include_deleted=False), "已加载全部便签")
        self.stateChanged.emit()

    @Slot(str)
    def loadCategory(self, category_key: str) -> None:
        self._active_category = category_key
        self._search_keyword = ""

        if category_key == "all":
            self.loadAll()
            return

        if category_key == "pinned":
            try:
                all_notes = self._fetch_notes(include_deleted=False)
                notes = [note for note in all_notes if note.is_pinned]
                self._set_notes(notes, "已加载置顶便签")
            except NotesApiError as exc:
                self._set_error(str(exc))
            self.stateChanged.emit()
            return

        tag = self._CATEGORY_TO_TAG.get(category_key)
        if tag:
            self._run_and_update(
                lambda: self._client.list_notes(include_deleted=False, tag=tag),
                f"已加载{tag}便签",
            )
        else:
            self.loadAll()

        self.stateChanged.emit()

    @Slot()
    def loadDeleted(self) -> None:
        self._active_category = "deleted"

        try:
            all_notes = self._fetch_notes(include_deleted=True)
            deleted = [note for note in all_notes if note.is_deleted]
            self.deleted_notes_model.set_notes(deleted)
            self._result_count = len(deleted)
            self._set_status("已加载已删除便签")
        except NotesApiError as exc:
            self.deleted_notes_model.set_notes([])
            self._set_error(str(exc))

        self.stateChanged.emit()

    @Slot(str)
    def searchNotes(self, keyword: str) -> None:
        query = keyword.strip()
        self._active_category = "search"
        self._search_keyword = query

        if not query:
            self.loadAll()
            return

        try:
            payload = self._client.search_notes(query=query, limit=100)
            notes = [note_from_api(item) for item in payload.get("items", [])]
            self._set_notes(notes, f"找到 {len(notes)} 条相关便签")
        except NotesApiError as exc:
            self._set_error(str(exc))
            self._set_notes([], "搜索失败")

        self.stateChanged.emit()

    @Slot(int)
    def selectNote(self, index: int) -> None:
        if 0 <= index < self.notes_model.count():
            self._selected_index = index
        else:
            self._selected_index = -1
        self.selectedChanged.emit()

    @Slot(str, str, str)
    def createNote(self, title: str, content: str, tags_text: str) -> None:
        clean_title = title.strip()
        clean_content = content.strip()

        if not clean_title:
            self._set_error("标题不能为空")
            return

        try:
            self._client.create_note(
                title=clean_title,
                content=clean_content,
                tags=_parse_tags(tags_text),
                source="manual",
            )
            self.loadAll()
            self._set_status("便签已保存")
        except NotesApiError as exc:
            self._set_error(str(exc))

    @Slot(str, str, str)
    def updateSelectedNote(self, title: str, content: str, tags_text: str) -> None:
        note = self._selected_note()
        if note is None:
            self._set_error("请先选择一条便签")
            return

        clean_title = title.strip()
        if not clean_title:
            self._set_error("标题不能为空")
            return

        try:
            self._client.update_note(
                note.id,
                title=clean_title,
                content=content.strip(),
                tags=_parse_tags(tags_text),
            )
            current_index = self._selected_index
            self.loadAll()
            self.selectNote(min(current_index, self.notes_model.count() - 1))
            self._set_status("便签已更新")
        except NotesApiError as exc:
            self._set_error(str(exc))

    @Slot()
    def deleteSelectedNote(self) -> None:
        note = self._selected_note()
        if note is None:
            self._set_error("请先选择一条便签")
            return

        try:
            self._client.delete_note(note.id)
            self.loadAll()
            self._set_status("便签已删除")
        except NotesApiError as exc:
            self._set_error(str(exc))

    @Slot()
    def testConnection(self) -> None:
        try:
            self._client.health()
            self._api_connected = True
            self._set_status("Notes API 已连接")
        except NotesApiError as exc:
            self._api_connected = False
            self._set_error(str(exc))
        self.statusChanged.emit()

    def _fetch_notes(self, *, include_deleted: bool) -> list[Note]:
        payload = self._client.list_notes(include_deleted=include_deleted, limit=200)
        return [note_from_api(item) for item in payload]

    def _run_and_update(self, fetcher, success_message: str) -> None:
        try:
            payload = fetcher()
            notes = [note_from_api(item) for item in payload]
            self._set_notes(notes, success_message)
        except NotesApiError as exc:
            self._set_error(str(exc))
            self._set_notes([], "加载失败")

    def _set_notes(self, notes: list[Note], status_message: str) -> None:
        self._current_notes = list(notes)
        self._all_notes_cache = list(notes)
        self.notes_model.set_notes(notes)
        self._result_count = len(notes)
        self._selected_index = 0 if notes else -1
        self._api_connected = True
        self._set_status(status_message)
        self.selectedChanged.emit()

    def _selected_note(self) -> Note | None:
        return self.notes_model.get_note(self._selected_index)

    def _set_status(self, message: str) -> None:
        self._status_message = message
        self._error_message = ""
        self.statusChanged.emit()

    def _set_error(self, message: str) -> None:
        self._error_message = message
        self._status_message = "操作失败"
        self._api_connected = False
        self.statusChanged.emit()


def _parse_tags(tags_text: str) -> list[str]:
    separators = [",", "，", "、", "·", "|", ";", "；"]
    normalized = tags_text

    for sep in separators:
        normalized = normalized.replace(sep, ",")

    return [tag.strip() for tag in normalized.split(",") if tag.strip()]
