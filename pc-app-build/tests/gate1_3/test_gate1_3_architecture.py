from __future__ import annotations

from dataclasses import fields
from pathlib import Path

from app.notes.migration import MigrationReport


def test_gate1_3_modules_do_not_import_qt() -> None:
    notes_root = (
        Path(__file__).resolve().parents[2] / "apps" / "notes-pyside" / "app" / "notes"
    )
    for filename in ("migration.py", "tag_catalog.py"):
        content = (notes_root / filename).read_text(encoding="utf-8")
        assert "PySide6" not in content
        assert "QtCore" not in content


def test_migration_report_contract_contains_no_note_body_fields() -> None:
    field_names = {field.name for field in fields(MigrationReport)}
    assert "title" not in field_names
    assert "content" not in field_names
    assert {
        "source_db",
        "target_db",
        "quick_check",
        "notes_count",
        "status",
        "error",
    }.issubset(field_names)
