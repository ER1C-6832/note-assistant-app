"""
Note data model and Qt list model for the PC App layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, Qt


UTC_PLUS_8 = timezone(timedelta(hours=8))


@dataclass(slots=True)
class Note:
    id: int
    title: str
    content: str
    tags: list[str]
    is_pinned: bool
    is_deleted: bool
    created_at: str
    updated_at: str
    source: str

    @property
    def tags_text(self) -> str:
        return " · ".join(self.tags) if self.tags else "未分类"

    @property
    def source_text(self) -> str:
        if self.source == "voice_pc":
            return "语音"
        if self.source == "voice_android":
            return "移动端语音"
        if self.source == "imported":
            return "导入"
        return "手动"

    @property
    def updated_text(self) -> str:
        return _format_datetime_gmt8(self.updated_at)

    @property
    def card_color(self) -> str:
        if self.is_deleted:
            return "#F3F4F6"
        if self.is_pinned:
            return "#FFF4C2"

        palette = [
            "#FFF4C2",
            "#DBEAFE",
            "#DCFCE7",
            "#FCE7F3",
            "#EDE9FE",
            "#CCFBF1",
            "#FFEDD5",
            "#FFE4E6",
            "#E0F2FE",
            "#FEF3C7",
            "#ECFDF5",
            "#F3E8FF",
        ]

        tag_palette = {
            "客户": 1,
            "报价": 8,
            "屏幕": 2,
            "样机": 9,
            "游戏手柄": 4,
            "测试": 6,
            "包装": 7,
            "待办": 3,
            "财务": 10,
            "会议": 5,
            "跟进": 0,
        }

        for tag in self.tags:
            if tag in tag_palette:
                return palette[tag_palette[tag]]

        return palette[self.id % len(palette)]


def _format_datetime_gmt8(value: str) -> str:
    if not value:
        return ""

    normalized = value.replace("Z", "+00:00")

    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return value[:16].replace("T", " ")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    local_dt = dt.astimezone(UTC_PLUS_8)
    return local_dt.strftime("%Y-%m-%d %H:%M")


def note_from_api(data: dict[str, Any]) -> Note:
    raw_tags = data.get("tags") or []
    tags = [str(item) for item in raw_tags if str(item).strip()]

    return Note(
        id=int(data.get("id", 0)),
        title=str(data.get("title") or ""),
        content=str(data.get("content") or ""),
        tags=tags,
        is_pinned=bool(data.get("is_pinned", False)),
        is_deleted=bool(data.get("is_deleted", False)),
        created_at=str(data.get("created_at") or ""),
        updated_at=str(data.get("updated_at") or ""),
        source=str(data.get("source") or "manual"),
    )


class NoteListModel(QAbstractListModel):
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

    def __init__(self) -> None:
        super().__init__()
        self._notes: list[Note] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._notes)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None

        row = index.row()
        if row < 0 or row >= len(self._notes):
            return None

        note = self._notes[row]

        if role == self.NoteIdRole:
            return note.id
        if role == self.TitleRole:
            return note.title
        if role == self.ContentRole:
            return note.content
        if role == self.TagsTextRole:
            return note.tags_text
        if role == self.UpdatedTextRole:
            return note.updated_text
        if role == self.SourceTextRole:
            return note.source_text
        if role == self.CardColorRole:
            return note.card_color
        if role == self.IsPinnedRole:
            return note.is_pinned
        if role == self.IsDeletedRole:
            return note.is_deleted

        return None

    def roleNames(self) -> dict[int, QByteArray]:
        return self._ROLE_NAMES

    def set_notes(self, notes: list[Note]) -> None:
        self.beginResetModel()
        self._notes = list(notes)
        self.endResetModel()

    def get_note(self, index: int) -> Note | None:
        if 0 <= index < len(self._notes):
            return self._notes[index]
        return None

    def count(self) -> int:
        return len(self._notes)
