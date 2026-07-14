"""Qt list model that exposes immutable note-domain objects to QML."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, Qt

from ..notes import Note, NoteSource

_SOURCE_TEXT = {
    NoteSource.MANUAL: "手动",
    NoteSource.VOICE_PC: "PC 语音",
    NoteSource.VOICE_ANDROID: "Android 语音",
    NoteSource.IMPORTED: "导入",
}
_CARD_COLORS = (
    "#FFF8E1",
    "#E8F5E9",
    "#E3F2FD",
    "#F3E5F5",
    "#FCE4EC",
    "#E0F7FA",
)


class NoteListModel(QAbstractListModel):
    """Read-only QML model backed only by :class:`Note` domain values."""

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

    def __init__(self, notes: Iterable[Note] = ()) -> None:
        super().__init__()
        self._notes = tuple(notes)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._notes)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or index.row() < 0 or index.row() >= len(self._notes):
            return None

        note = self._notes[index.row()]
        if role == self.NoteIdRole:
            return note.id
        if role in (Qt.DisplayRole, self.TitleRole):
            return note.title
        if role == self.ContentRole:
            return note.content
        if role == self.TagsTextRole:
            return "、".join(note.tags)
        if role == self.UpdatedTextRole:
            return _format_datetime(note.updated_at)
        if role == self.SourceTextRole:
            return _SOURCE_TEXT.get(note.source, str(note.source))
        if role == self.CardColorRole:
            return _CARD_COLORS[(note.id - 1) % len(_CARD_COLORS)]
        if role == self.IsPinnedRole:
            return note.is_pinned
        if role == self.IsDeletedRole:
            return note.is_deleted
        return None

    def roleNames(self) -> dict[int, QByteArray]:
        return dict(self._ROLE_NAMES)

    @property
    def notes(self) -> tuple[Note, ...]:
        return self._notes

    def replace_notes(self, notes: Iterable[Note]) -> None:
        replacement = tuple(notes)
        if replacement == self._notes:
            return
        self.beginResetModel()
        self._notes = replacement
        self.endResetModel()

    def note_at(self, index: int) -> Note | None:
        if index < 0 or index >= len(self._notes):
            return None
        return self._notes[index]

    def note_by_id(self, note_id: int | None) -> Note | None:
        if note_id is None:
            return None
        return next((note for note in self._notes if note.id == note_id), None)

    def index_of_id(self, note_id: int | None) -> int:
        if note_id is None:
            return -1
        for index, note in enumerate(self._notes):
            if note.id == note_id:
                return index
        return -1

    def note_ids(self) -> list[int]:
        return [note.id for note in self._notes]

    def first_note_id(self) -> int | None:
        return self._notes[0].id if self._notes else None


def _format_datetime(value: datetime) -> str:
    local_value = value.astimezone()
    return local_value.strftime("%Y-%m-%d %H:%M")
