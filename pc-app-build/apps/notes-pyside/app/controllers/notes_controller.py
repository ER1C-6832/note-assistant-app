"""
Notes controller exposed to QML.

Hotfix focus:
- Stable sidebar tag list that does not shrink after filtering.
- Tags discovered from notes are persisted locally, so they remain visible even
  after all related notes are permanently deleted.
"""

from __future__ import annotations

import json
from pathlib import Path
from threading import Thread
from typing import Any, Callable

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.models.note import Note, NoteListModel, note_from_api
from app.services.notes_api_client import (
    NotesApiClient,
    NotesApiConnectionError,
    NotesApiError,
    NotesApiHttpError,
)


class NotesController(QObject):
    stateChanged = Signal()
    selectedChanged = Signal()
    statusChanged = Signal()
    tagsChanged = Signal()
    _asyncSuccess = Signal(int, str, object, str)
    _asyncError = Signal(int, object)

    _PROTECTED_TAGS = {"待办"}
    _DEFAULT_TAGS = [
        "客户",
        "报价",
        "屏幕",
        "样机",
        "游戏手柄",
        "测试",
        "包装",
        "跟进",
    ]

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
        self._request_token = 0
        self._all_known_notes: list[Note] = []
        self._custom_tags = self._load_custom_tags()
        self._ensure_default_tags()
        self._visible_tags = self._build_tag_list()

        self._asyncSuccess.connect(self._handle_async_success)
        self._asyncError.connect(self._handle_async_error)

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

    @Property("QVariantList", notify=tagsChanged)
    def tagNames(self) -> list[str]:
        return list(self._visible_tags)

    @Slot()
    def refresh(self) -> None:
        self._reload_current_view()

    @Slot()
    def loadAll(self) -> None:
        self._active_category = "all"
        self._search_keyword = ""
        self._start_fetch(
            "all",
            lambda: self._client.list_notes(include_deleted=True),
            "已加载全部便签",
        )
        self.stateChanged.emit()

    @Slot(str)
    def loadCategory(self, category_key: str) -> None:
        self._active_category = category_key
        self._search_keyword = ""

        if category_key == "all":
            self.loadAll()
            return

        if category_key == "pinned":
            self._start_fetch(
                "pinned",
                lambda: self._client.list_notes(include_deleted=True),
                "已加载置顶便签",
            )
            self.stateChanged.emit()
            return

        if category_key == "todo":
            self.loadTag("待办")
            return

        if category_key.startswith("tag:"):
            self.loadTag(category_key[4:])
            return

        self.loadAll()

    @Slot(str)
    def loadTag(self, tag: str) -> None:
        clean_tag = tag.strip()
        if not clean_tag:
            self.loadAll()
            return

        self._active_category = f"tag:{clean_tag}"
        self._search_keyword = ""
        self._start_fetch(
            f"tag:{clean_tag}",
            lambda: self._client.list_notes(include_deleted=True),
            f"已加载{clean_tag}便签",
        )
        self.stateChanged.emit()

    @Slot()
    def loadDeleted(self) -> None:
        self._active_category = "deleted"
        self._start_fetch(
            "deleted",
            lambda: self._client.list_notes(include_deleted=True),
            "已加载已删除便签",
        )
        self.stateChanged.emit()

    @Slot(str)
    def searchNotes(self, keyword: str) -> None:
        query = keyword.strip()
        self._active_category = "search"
        self._search_keyword = query

        if not query:
            self.loadAll()
            return

        self._start_fetch(
            "search",
            lambda: self._client.search_notes(query=query, limit=100),
            "搜索完成",
        )
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
            self._reload_current_view()
            return True
        except NotesApiError as exc:
            self._handle_error(exc)
            return False
        finally:
            self._set_busy(False)

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

    @Slot(int, result=bool)
    def restoreDeletedNoteAt(self, index: int) -> bool:
        note = self.deleted_notes_model.get_note(index)
        if note is None:
            self._set_error("请先选择一条已删除便签")
            return False
        return self.bulkRestoreDeletedNotesByIds([note.id])

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

    @Slot(str, result=bool)
    def addCustomTag(self, tag: str) -> bool:
        clean_tag = tag.strip()
        if not clean_tag:
            self._set_error("标签不能为空")
            return False

        if clean_tag in {"全部", "置顶", "已删除"}:
            self._set_error("不能使用系统分类名称")
            return False

        if clean_tag not in self._custom_tags:
            self._custom_tags.append(clean_tag)
            self._custom_tags = sorted(set(self._custom_tags))
            self._save_custom_tags()
            self._visible_tags = self._build_tag_list()
            self.tagsChanged.emit()
            self._set_status("标签已添加")
        return True

    @Slot(str, result=bool)
    def deleteTag(self, tag: str) -> bool:
        clean_tag = tag.strip()
        if not clean_tag:
            return False

        if clean_tag in self._PROTECTED_TAGS:
            self._set_error("该标签不能删除")
            return False

        for note in self._all_known_notes:
            if clean_tag in note.tags:
                self._set_error("该标签下还有便签，不能删除")
                return False

        if clean_tag in self._custom_tags:
            self._custom_tags.remove(clean_tag)
            self._save_custom_tags()

        self._visible_tags = self._build_tag_list()
        self.tagsChanged.emit()
        self._set_status("标签已删除")
        return True

    @Slot(str, result=bool)
    def tagCanDelete(self, tag: str) -> bool:
        clean_tag = tag.strip()

        if not clean_tag or clean_tag in self._PROTECTED_TAGS:
            return False

        for note in self._all_known_notes:
            if clean_tag in note.tags:
                return False

        return clean_tag in self._custom_tags

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

    def _start_fetch(self, kind: str, fetcher: Callable[[], Any], success_message: str) -> None:
        self._request_token += 1
        token = self._request_token
        self._set_busy(True)

        def worker() -> None:
            try:
                result = fetcher()
            except NotesApiError as exc:
                self._asyncError.emit(token, exc)
                return
            self._asyncSuccess.emit(token, kind, result, success_message)

        Thread(target=worker, daemon=True).start()

    def _handle_async_success(self, token: int, kind: str, result: object, success_message: str) -> None:
        if token != self._request_token:
            return

        try:
            if kind == "search":
                payload = result if isinstance(result, dict) else {}
                notes = [note_from_api(item) for item in payload.get("items", [])]
                self._set_notes(notes, f"找到 {len(notes)} 条相关便签")
            else:
                items = result if isinstance(result, list) else []
                all_notes = [note_from_api(item) for item in items]
                self._all_known_notes = all_notes
                self._persist_observed_tags(all_notes)

                if kind == "deleted":
                    deleted = [note for note in all_notes if note.is_deleted]
                    self.deleted_notes_model.set_notes(deleted)
                    self._deleted_result_count = len(deleted)
                    self._result_count = len(deleted)
                    self._deleted_selected_index = 0 if deleted else -1
                    self._selected_index = -1
                    self._set_status(success_message)
                    self.selectedChanged.emit()
                elif kind == "pinned":
                    self._set_notes(
                        [note for note in all_notes if not note.is_deleted and note.is_pinned],
                        success_message,
                    )
                elif kind.startswith("tag:"):
                    tag = kind[4:]
                    self._set_notes(
                        [note for note in all_notes if not note.is_deleted and tag in note.tags],
                        success_message,
                    )
                else:
                    self._set_notes(
                        [note for note in all_notes if not note.is_deleted],
                        success_message,
                    )

            self._set_connected()
        finally:
            self._set_busy(False)
            self.stateChanged.emit()

    def _handle_async_error(self, token: int, exc: object) -> None:
        if token != self._request_token:
            return

        if isinstance(exc, NotesApiError):
            self._handle_error(exc)
        else:
            self._set_error(str(exc))

        self._set_busy(False)
        self.stateChanged.emit()

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

    def _persist_observed_tags(self, notes: list[Note]) -> None:
        observed = set(self._custom_tags)

        for note in notes:
            for tag in note.tags:
                clean_tag = tag.strip()
                if clean_tag and clean_tag not in self._PROTECTED_TAGS:
                    observed.add(clean_tag)

        new_custom_tags = sorted(observed)

        if new_custom_tags != self._custom_tags:
            self._custom_tags = new_custom_tags
            self._save_custom_tags()

        self._visible_tags = self._build_tag_list()
        self.tagsChanged.emit()

    def _build_tag_list(self) -> list[str]:
        return sorted(
            tag for tag in set(self._custom_tags)
            if tag and tag not in self._PROTECTED_TAGS
        )

    def _ensure_default_tags(self) -> None:
        merged = set(self._custom_tags)

        for tag in self._DEFAULT_TAGS:
            if tag not in self._PROTECTED_TAGS:
                merged.add(tag)

        self._custom_tags = sorted(merged)
        self._save_custom_tags()

    def _tag_store_path(self) -> Path:
        app_root = Path(__file__).resolve().parents[1]
        return app_root / "data" / "custom_tags.json"

    def _load_custom_tags(self) -> list[str]:
        path = self._tag_store_path()
        if not path.exists():
            return []

        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

        if not isinstance(value, list):
            return []

        return sorted({str(item).strip() for item in value if str(item).strip()})

    def _save_custom_tags(self) -> None:
        path = self._tag_store_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._custom_tags, ensure_ascii=False, indent=2), encoding="utf-8")


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
