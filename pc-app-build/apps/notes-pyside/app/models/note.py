"""Note data model and Qt list model for the PC App layer."""
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
        return {"voice_pc": "语音", "voice_android": "移动端语音", "imported": "导入"}.get(self.source, "手动")

    @property
    def updated_text(self) -> str:
        return _format_datetime_gmt8(self.updated_at)

    @property
    def card_color(self) -> str:
        if self.is_deleted: return "#F3F4F6"
        if self.is_pinned: return "#FFF7D6"
        tag_color_map = {"客户":"#E9F2FF","报价":"#EAF0FF","屏幕":"#E8F9F1","样机":"#E0F2FE","游戏手柄":"#F5E8FF","测试":"#FEF3C7","包装":"#FFE4E6","待办":"#FCE9F3","财务":"#ECFDF3","会议":"#EEF2FF"}
        for tag in self.tags:
            if tag in tag_color_map: return tag_color_map[tag]
        palette = ["#FFF6CC", "#E9F2FF", "#E8F9F1", "#FCE9F3", "#F5E8FF", "#E0F2FE", "#FEF3C7", "#FFE4E6"]
        return palette[self.id % len(palette)]

def _format_datetime_gmt8(value: str) -> str:
    if not value: return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value[:16].replace("T", " ")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(UTC_PLUS_8).strftime("%Y-%m-%d %H:%M")

def note_from_api(data: dict[str, Any]) -> Note:
    tags = [str(item) for item in (data.get("tags") or []) if str(item).strip()]
    return Note(id=int(data.get("id", 0)), title=str(data.get("title") or ""), content=str(data.get("content") or ""), tags=tags, is_pinned=bool(data.get("is_pinned", False)), is_deleted=bool(data.get("is_deleted", False)), created_at=str(data.get("created_at") or ""), updated_at=str(data.get("updated_at") or ""), source=str(data.get("source") or "manual"))

class NoteListModel(QAbstractListModel):
    NoteIdRole = Qt.UserRole + 1; TitleRole = Qt.UserRole + 2; ContentRole = Qt.UserRole + 3; TagsTextRole = Qt.UserRole + 4; UpdatedTextRole = Qt.UserRole + 5; SourceTextRole = Qt.UserRole + 6; CardColorRole = Qt.UserRole + 7; IsPinnedRole = Qt.UserRole + 8; IsDeletedRole = Qt.UserRole + 9
    _ROLE_NAMES = {NoteIdRole: QByteArray(b"noteId"), TitleRole: QByteArray(b"title"), ContentRole: QByteArray(b"content"), TagsTextRole: QByteArray(b"tagsText"), UpdatedTextRole: QByteArray(b"updatedText"), SourceTextRole: QByteArray(b"sourceText"), CardColorRole: QByteArray(b"cardColor"), IsPinnedRole: QByteArray(b"isPinned"), IsDeletedRole: QByteArray(b"isDeleted")}
    def __init__(self) -> None:
        super().__init__(); self._notes: list[Note] = []
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._notes)
    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or index.row() < 0 or index.row() >= len(self._notes): return None
        n = self._notes[index.row()]
        return {self.NoteIdRole:n.id,self.TitleRole:n.title,self.ContentRole:n.content,self.TagsTextRole:n.tags_text,self.UpdatedTextRole:n.updated_text,self.SourceTextRole:n.source_text,self.CardColorRole:n.card_color,self.IsPinnedRole:n.is_pinned,self.IsDeletedRole:n.is_deleted}.get(role)
    def roleNames(self) -> dict[int, QByteArray]: return self._ROLE_NAMES
    def set_notes(self, notes: list[Note]) -> None:
        self.beginResetModel(); self._notes = list(notes); self.endResetModel()
    def get_note(self, index: int) -> Note | None:
        return self._notes[index] if 0 <= index < len(self._notes) else None
    def get_note_by_id(self, note_id: int) -> Note | None:
        return next((n for n in self._notes if n.id == note_id), None)
    def count(self) -> int: return len(self._notes)
