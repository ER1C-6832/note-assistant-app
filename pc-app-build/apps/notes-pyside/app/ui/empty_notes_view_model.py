"""Temporary Gate 1.1 view model used only to validate application composition."""

from __future__ import annotations

from PySide6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    Property,
    Qt,
    Signal,
    Slot,
)


class EmptyNoteListModel(QAbstractListModel):
    NoteIdRole = Qt.UserRole + 1
    TitleRole = Qt.UserRole + 2
    ContentRole = Qt.UserRole + 3
    TagsTextRole = Qt.UserRole + 4
    UpdatedTextRole = Qt.UserRole + 5
    SourceTextRole = Qt.UserRole + 6
    CardColorRole = Qt.UserRole + 7
    IsPinnedRole = Qt.UserRole + 8
    IsDeletedRole = Qt.UserRole + 9

    _ROLE_NAMES = {
        NoteIdRole: QByteArray(b"noteId"),
        TitleRole: QByteArray(b"title"),
        ContentRole: QByteArray(b"content"),
        TagsTextRole: QByteArray(b"tagsText"),
        UpdatedTextRole: QByteArray(b"updatedText"),
        SourceTextRole: QByteArray(b"sourceText"),
        CardColorRole: QByteArray(b"cardColor"),
        IsPinnedRole: QByteArray(b"isPinned"),
        IsDeletedRole: QByteArray(b"isDeleted"),
    }

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if not parent.isValid() else 0

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        return None

    def roleNames(self) -> dict[int, QByteArray]:
        return self._ROLE_NAMES


class EmptyNotesViewModel(QObject):
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

    def __init__(self) -> None:
        super().__init__()
        self._active_category = "all"
        self._search_keyword = ""
        self._status_message = "Gate 1.1 启动骨架已就绪"
        self._error_message = ""

    @Property(int, notify=selectedChanged)
    def selectedIndex(self) -> int:
        return -1

    @Property(bool, notify=selectedChanged)
    def hasSelection(self) -> bool:
        return False

    @Property(str, notify=selectedChanged)
    def selectedTitle(self) -> str:
        return ""

    @Property(str, notify=selectedChanged)
    def selectedContent(self) -> str:
        return ""

    @Property(str, notify=selectedChanged)
    def selectedTagsText(self) -> str:
        return ""

    @Property(str, notify=selectedChanged)
    def selectedSourceText(self) -> str:
        return ""

    @Property(str, notify=selectedChanged)
    def selectedUpdatedText(self) -> str:
        return ""

    @Property(bool, notify=selectedChanged)
    def selectedIsPinned(self) -> bool:
        return False

    @Property(int, notify=selectedChanged)
    def deletedSelectedIndex(self) -> int:
        return -1

    @Property(str, notify=stateChanged)
    def activeCategory(self) -> str:
        return self._active_category

    @Property(str, notify=stateChanged)
    def searchKeyword(self) -> str:
        return self._search_keyword

    @Property(int, notify=stateChanged)
    def resultCount(self) -> int:
        return 0

    @Property(int, notify=stateChanged)
    def deletedResultCount(self) -> int:
        return 0

    @Property(str, notify=statusChanged)
    def statusMessage(self) -> str:
        return self._status_message

    @Property(str, notify=statusChanged)
    def errorMessage(self) -> str:
        return self._error_message

    @Property(bool, notify=statusChanged)
    def isBusy(self) -> bool:
        return False

    @Property(bool, notify=statusChanged)
    def mutationBusy(self) -> bool:
        return False

    @Property("QVariantList", notify=tagsChanged)
    def tagItems(self) -> list[dict[str, object]]:
        return []

    @Slot()
    def loadAll(self) -> None:
        self._set_query_state("all", "", "Gate 1.1：空便签列表已加载")

    @Slot(str)
    def loadCategory(self, category_key: str) -> None:
        category = category_key.strip() or "all"
        self._set_query_state(category, "", f"Gate 1.1：已切换到 {category}")

    @Slot(str)
    def loadTag(self, tag: str) -> None:
        clean_tag = tag.strip()
        category = f"tag:{clean_tag}" if clean_tag else "all"
        self._set_query_state(category, "", "Gate 1.1：标签查询尚未接入数据库")

    @Slot()
    def loadDeleted(self) -> None:
        self._set_query_state("deleted", "", "Gate 1.1：已删除列表尚未接入数据库")

    @Slot(str)
    def searchNotes(self, keyword: str) -> None:
        query = keyword.strip()
        category = "search" if query else "all"
        self._set_query_state(category, query, "Gate 1.1：搜索尚未接入数据库")

    @Slot()
    def refreshCurrentView(self) -> None:
        self.statusChanged.emit()

    @Slot(int)
    def selectNote(self, index: int) -> None:
        self.selectedChanged.emit()

    @Slot(int)
    def selectDeletedNote(self, index: int) -> None:
        self.selectedChanged.emit()

    @Slot(result="QVariantList")
    def currentNoteIds(self) -> list[int]:
        return []

    @Slot(result="QVariantList")
    def currentDeletedNoteIds(self) -> list[int]:
        return []

    @Slot(str, str, str, bool)
    def requestCreateNote(
        self,
        title: str,
        content: str,
        tags_text: str,
        is_pinned: bool,
    ) -> None:
        self._reject_mutation("create", "Gate 1.1 尚未接入数据库，暂时不能创建便签")

    @Slot(str, str, str)
    def requestUpdateSelectedNote(
        self,
        title: str,
        content: str,
        tags_text: str,
    ) -> None:
        self._reject_mutation("update", "Gate 1.1 尚未接入数据库，暂时不能修改便签")

    @Slot()
    def requestDeleteSelectedNote(self) -> None:
        self._reject_mutation("delete", "Gate 1.1 尚未接入数据库，暂时不能删除便签")

    @Slot()
    def requestToggleSelectedPin(self) -> None:
        self._reject_mutation("toggle_pin", "Gate 1.1 尚未接入数据库，暂时不能置顶便签")

    @Slot("QVariantList")
    def requestBulkDelete(self, note_ids) -> None:
        self._reject_mutation("bulk_delete", "Gate 1.1 尚未接入数据库")

    @Slot("QVariantList")
    def requestBulkPin(self, note_ids) -> None:
        self._reject_mutation("bulk_pin", "Gate 1.1 尚未接入数据库")

    @Slot("QVariantList")
    def requestBulkUnpin(self, note_ids) -> None:
        self._reject_mutation("bulk_unpin", "Gate 1.1 尚未接入数据库")

    @Slot(int)
    def requestRestoreDeletedAt(self, index: int) -> None:
        self._reject_mutation("restore", "Gate 1.1 尚未接入数据库")

    @Slot("QVariantList")
    def requestBulkRestoreDeleted(self, note_ids) -> None:
        self._reject_mutation("bulk_restore", "Gate 1.1 尚未接入数据库")

    @Slot("QVariantList")
    def requestBulkHardDeleteDeleted(self, note_ids) -> None:
        self._reject_mutation("bulk_hard_delete", "Gate 1.1 尚未接入数据库")

    @Slot(str)
    def requestAddCustomTag(self, tag: str) -> None:
        self._reject_mutation("add_tag", "Gate 1.1 尚未接入标签目录")

    @Slot(str)
    def requestDeleteTag(self, tag: str) -> None:
        self._reject_mutation("delete_tag", "Gate 1.1 尚未接入标签目录")

    def _set_query_state(self, category: str, keyword: str, message: str) -> None:
        self._active_category = category
        self._search_keyword = keyword
        self._status_message = message
        self._error_message = ""
        self.stateChanged.emit()
        self.statusChanged.emit()

    def _reject_mutation(self, operation: str, message: str) -> None:
        self._status_message = "功能尚未接入"
        self._error_message = message
        self.statusChanged.emit()
        self.operationFailed.emit(operation, message)
