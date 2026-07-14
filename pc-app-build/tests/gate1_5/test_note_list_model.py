from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import Qt

from app.notes import Note, NoteSource
from app.ui.note_list_model import NoteListModel


def make_note(note_id: int, *, title: str = "标题", pinned: bool = False) -> Note:
    now = datetime(2026, 7, 14, 12, 30, tzinfo=timezone.utc)
    return Note(
        id=note_id,
        title=title,
        content="正文",
        tags=("客户", "跟进"),
        is_pinned=pinned,
        is_deleted=False,
        created_at=now,
        updated_at=now,
        source=NoteSource.MANUAL,
    )


def test_fixed_roles_expose_domain_note_values() -> None:
    model = NoteListModel((make_note(1, pinned=True),))
    index = model.index(0, 0)

    assert model.rowCount() == 1
    assert model.data(index, NoteListModel.NoteIdRole) == 1
    assert model.data(index, Qt.DisplayRole) == "标题"
    assert model.data(index, NoteListModel.ContentRole) == "正文"
    assert model.data(index, NoteListModel.TagsTextRole) == "客户、跟进"
    assert model.data(index, NoteListModel.SourceTextRole) == "手动"
    assert model.data(index, NoteListModel.IsPinnedRole) is True
    assert model.data(index, NoteListModel.IsDeletedRole) is False
    assert model.roleNames()[NoteListModel.NoteIdRole].data() == b"noteId"


def test_replace_and_lookup_are_note_id_based() -> None:
    model = NoteListModel((make_note(1), make_note(2)))

    assert model.index_of_id(2) == 1
    assert model.note_at(1).id == 2
    assert model.note_ids() == [1, 2]

    model.replace_notes((make_note(2, title="更新"), make_note(3)))

    assert model.index_of_id(2) == 0
    assert model.note_by_id(2).title == "更新"
    assert model.note_by_id(1) is None
