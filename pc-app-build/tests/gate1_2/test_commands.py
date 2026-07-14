from __future__ import annotations

import pytest

from app.notes.commands import (
    CreateNoteCommand,
    NoteValidationError,
    SetPinnedCommand,
    normalize_tags,
)
from app.notes.domain import NoteSource


def test_create_command_normalizes_values() -> None:
    command = CreateNoteCommand(
        title="  标题  ",
        content="正文\n\n  ",
        tags=(" 客户 ", "客户", "", " 跟进 "),
        source="voice_pc",
    )
    assert command.title == "标题"
    assert command.content == "正文"
    assert command.tags == ("客户", "跟进")
    assert command.source is NoteSource.VOICE_PC


def test_empty_title_is_rejected() -> None:
    with pytest.raises(NoteValidationError):
        CreateNoteCommand(title="   ", content="", tags=())


def test_title_length_is_limited() -> None:
    with pytest.raises(NoteValidationError):
        CreateNoteCommand(title="x" * 201, content="", tags=())


def test_bulk_ids_are_positive_unique_and_ordered() -> None:
    command = SetPinnedCommand(note_ids=(3, 1, 3, 2), is_pinned=True)
    assert command.note_ids == (3, 1, 2)


@pytest.mark.parametrize("values", [(), (0,), (-1,), (True,)])
def test_invalid_bulk_ids_are_rejected(values) -> None:
    with pytest.raises(NoteValidationError):
        SetPinnedCommand(note_ids=values, is_pinned=True)


def test_tag_normalization_preserves_first_occurrence_order() -> None:
    assert normalize_tags(["B", " A ", "B", "C"]) == ("B", "A", "C")
