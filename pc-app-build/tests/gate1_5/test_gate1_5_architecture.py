from __future__ import annotations

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "apps" / "notes-pyside" / "app"


def test_view_model_depends_on_services_not_sqlalchemy_or_repository() -> None:
    source = (APP_ROOT / "ui" / "notes_view_model.py").read_text(encoding="utf-8")

    assert "sqlalchemy" not in source.lower()
    assert "Session" not in source
    assert "SqlAlchemyNoteRepository" not in source
    assert "NoteCommandService" in source
    assert "NoteQueryService" in source


def test_model_accepts_domain_notes_and_has_fixed_roles() -> None:
    source = (APP_ROOT / "ui" / "note_list_model.py").read_text(encoding="utf-8")

    for role in (
        "noteId",
        "title",
        "content",
        "tagsText",
        "updatedText",
        "sourceText",
        "cardColor",
        "isPinned",
        "isDeleted",
    ):
        assert role in source
    assert "NoteRow" not in source
    assert "Iterable[Note]" in source
