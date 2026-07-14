from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from app.app_paths import AppPaths
from app.notes.migration import (
    LEGACY_DB_ENV,
    LEGACY_TAGS_ENV,
    DatabaseValidationError,
    LegacySchemaError,
    MigrationConflictError,
    TagFileValidationError,
    inspect_database,
    prepare_gate1_local_data,
)
from app.notes.sqlalchemy_repository import (
    create_sqlite_engine,
    initialize_database,
)

from migration_test_support import create_legacy_database


def _clock(value):
    return lambda: value


def test_no_source_creates_empty_database_and_first_run_backup(
    app_paths: AppPaths,
    worktree_root: Path,
    fixed_now,
) -> None:
    result = prepare_gate1_local_data(
        app_paths,
        worktree_root=worktree_root,
        env={},
        now_provider=_clock(fixed_now),
    )

    assert result.status == "created_empty"
    assert result.notes_count == 0
    assert result.source_db is None
    assert result.backup_db is not None and result.backup_db.is_file()
    assert inspect_database(app_paths.notes_db).notes_count == 0

    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert report["status"] == "created_empty"
    assert report["quick_check"] == "ok"
    assert report["notes_count"] == 0
    assert "legacy note" not in result.report_path.read_text(encoding="utf-8")


def test_single_source_and_tag_file_are_migrated_without_deleting_sources(
    app_paths: AppPaths,
    worktree_root: Path,
    tmp_path: Path,
    fixed_now,
) -> None:
    source_db = tmp_path / "legacy" / "notes.db"
    source_tags = tmp_path / "legacy" / "custom_tags.json"
    create_legacy_database(source_db, note_titles=("first", "second"))
    source_tags.write_text(
        json.dumps([" 客户 ", "跟进", "客户"], ensure_ascii=False),
        encoding="utf-8",
    )

    result = prepare_gate1_local_data(
        app_paths,
        worktree_root=worktree_root,
        env={
            LEGACY_DB_ENV: str(source_db),
            LEGACY_TAGS_ENV: str(source_tags),
        },
        now_provider=_clock(fixed_now),
    )

    assert result.status == "migrated"
    assert result.source_db == source_db.resolve()
    assert result.tags_source == source_tags.resolve()
    assert result.notes_count == 2
    assert source_db.is_file()
    assert source_tags.is_file()
    assert json.loads(app_paths.custom_tags.read_text(encoding="utf-8")) == [
        "客户",
        "跟进",
    ]
    assert inspect_database(app_paths.notes_db).notes_count == 2


def test_multiple_distinct_database_candidates_are_not_guessed(
    app_paths: AppPaths,
    worktree_root: Path,
    tmp_path: Path,
    fixed_now,
) -> None:
    configured = tmp_path / "configured.db"
    current_legacy = worktree_root / "pc-app-build" / "services" / "notes-api" / "data" / "notes.db"
    create_legacy_database(configured)
    create_legacy_database(current_legacy)

    with pytest.raises(MigrationConflictError) as captured:
        prepare_gate1_local_data(
            app_paths,
            worktree_root=worktree_root,
            env={LEGACY_DB_ENV: str(configured)},
            now_provider=_clock(fixed_now),
        )

    assert captured.value.kind == "database"
    assert len(captured.value.candidates) == 2
    assert not app_paths.notes_db.exists()
    report = json.loads((app_paths.logs_dir / "migration-gate1.json").read_text("utf-8"))
    assert report["status"] == "failed"


def test_corrupt_source_is_rejected_and_left_untouched(
    app_paths: AppPaths,
    worktree_root: Path,
    tmp_path: Path,
    fixed_now,
) -> None:
    source = tmp_path / "broken.db"
    payload = b"not a sqlite database"
    source.write_bytes(payload)

    with pytest.raises(DatabaseValidationError):
        prepare_gate1_local_data(
            app_paths,
            worktree_root=worktree_root,
            env={LEGACY_DB_ENV: str(source)},
            now_provider=_clock(fixed_now),
        )

    assert source.read_bytes() == payload
    assert not app_paths.notes_db.exists()


def test_source_with_missing_columns_is_rejected(
    app_paths: AppPaths,
    worktree_root: Path,
    tmp_path: Path,
    fixed_now,
) -> None:
    source = tmp_path / "old-schema.db"
    create_legacy_database(source, include_source=False)

    with pytest.raises(LegacySchemaError) as captured:
        prepare_gate1_local_data(
            app_paths,
            worktree_root=worktree_root,
            env={LEGACY_DB_ENV: str(source)},
            now_provider=_clock(fixed_now),
        )

    assert captured.value.missing_columns == ("source",)
    assert source.exists()


def test_existing_valid_target_is_never_overwritten_by_legacy_candidate(
    app_paths: AppPaths,
    worktree_root: Path,
    tmp_path: Path,
    fixed_now,
) -> None:
    create_legacy_database(app_paths.notes_db, note_titles=("target",))
    source = tmp_path / "legacy.db"
    create_legacy_database(source, note_titles=("source one", "source two"))

    result = prepare_gate1_local_data(
        app_paths,
        worktree_root=worktree_root,
        env={LEGACY_DB_ENV: str(source)},
        now_provider=_clock(fixed_now),
    )

    assert result.status == "existing"
    assert result.source_db is None
    assert inspect_database(app_paths.notes_db).notes_count == 1
    with sqlite3.connect(app_paths.notes_db) as connection:
        assert connection.execute("SELECT title FROM notes").fetchone()[0] == "target"


def test_corrupt_existing_target_is_backed_up_and_blocks_startup(
    app_paths: AppPaths,
    worktree_root: Path,
    fixed_now,
) -> None:
    payload = b"corrupt local database"
    app_paths.notes_db.write_bytes(payload)

    with pytest.raises(DatabaseValidationError):
        prepare_gate1_local_data(
            app_paths,
            worktree_root=worktree_root,
            env={},
            now_provider=_clock(fixed_now),
        )

    backups = list(app_paths.backups_dir.glob("notes-corrupt-*.db"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == payload
    assert app_paths.notes_db.read_bytes() == payload


def test_invalid_legacy_tag_file_is_rejected_without_overwrite(
    app_paths: AppPaths,
    worktree_root: Path,
    tmp_path: Path,
    fixed_now,
) -> None:
    source_tags = tmp_path / "invalid-tags.json"
    source_tags.write_text('{"tag": "客户"}', encoding="utf-8")

    with pytest.raises(TagFileValidationError):
        prepare_gate1_local_data(
            app_paths,
            worktree_root=worktree_root,
            env={LEGACY_TAGS_ENV: str(source_tags)},
            now_provider=_clock(fixed_now),
        )

    assert source_tags.read_text(encoding="utf-8") == '{"tag": "客户"}'
    assert not app_paths.custom_tags.exists()


def test_preparation_is_idempotent_and_does_not_create_repeated_backups(
    app_paths: AppPaths,
    worktree_root: Path,
    fixed_now,
) -> None:
    first = prepare_gate1_local_data(
        app_paths,
        worktree_root=worktree_root,
        env={},
        now_provider=_clock(fixed_now),
    )
    second = prepare_gate1_local_data(
        app_paths,
        worktree_root=worktree_root,
        env={},
        now_provider=_clock(fixed_now),
    )

    assert first.status == "created_empty"
    assert second.status == "existing"
    assert second.backup_db is None
    assert len(list(app_paths.backups_dir.glob("notes-pre-gate1-*.db"))) == 1


def test_existing_database_created_by_current_schema_passes_inspection(
    app_paths: AppPaths,
) -> None:
    engine = create_sqlite_engine(app_paths.notes_db)
    try:
        initialize_database(engine)
    finally:
        engine.dispose()

    inspection = inspect_database(app_paths.notes_db)
    assert inspection.quick_check == "ok"
    assert inspection.notes_count == 0


def test_same_database_candidate_is_deduplicated(
    app_paths: AppPaths,
    worktree_root: Path,
    fixed_now,
) -> None:
    source = worktree_root / "pc-app-build" / "services" / "notes-api" / "data" / "notes.db"
    create_legacy_database(source)

    result = prepare_gate1_local_data(
        app_paths,
        worktree_root=worktree_root,
        env={LEGACY_DB_ENV: str(source)},
        now_provider=_clock(fixed_now),
    )

    assert result.status == "migrated"
    assert result.source_db == source.resolve()
    assert result.notes_count == 1


def test_sibling_legacy_tag_file_precedes_current_transition_copy(
    app_paths: AppPaths,
    worktree_root: Path,
    fixed_now,
) -> None:
    current_tags = (
        worktree_root
        / "pc-app-build"
        / "apps"
        / "notes-pyside"
        / "app"
        / "data"
        / "custom_tags.json"
    )
    sibling_tags = (
        worktree_root.parent
        / "note-assistant-app"
        / "pc-app-build"
        / "apps"
        / "notes-pyside"
        / "app"
        / "data"
        / "custom_tags.json"
    )
    current_tags.parent.mkdir(parents=True, exist_ok=True)
    sibling_tags.parent.mkdir(parents=True, exist_ok=True)
    current_tags.write_text('["当前过渡副本"]', encoding="utf-8")
    sibling_tags.write_text('["旧仓库标签"]', encoding="utf-8")

    result = prepare_gate1_local_data(
        app_paths,
        worktree_root=worktree_root,
        env={},
        now_provider=_clock(fixed_now),
    )

    assert result.tags_source == sibling_tags.resolve()
    assert json.loads(app_paths.custom_tags.read_text(encoding="utf-8")) == ["旧仓库标签"]
    assert current_tags.read_text(encoding="utf-8") == '["当前过渡副本"]'
    assert sibling_tags.read_text(encoding="utf-8") == '["旧仓库标签"]'


def test_current_transition_tag_file_is_fallback_when_sibling_is_missing(
    app_paths: AppPaths,
    worktree_root: Path,
    fixed_now,
) -> None:
    current_tags = (
        worktree_root
        / "pc-app-build"
        / "apps"
        / "notes-pyside"
        / "app"
        / "data"
        / "custom_tags.json"
    )
    current_tags.parent.mkdir(parents=True, exist_ok=True)
    current_tags.write_text('["过渡标签"]', encoding="utf-8")

    result = prepare_gate1_local_data(
        app_paths,
        worktree_root=worktree_root,
        env={},
        now_provider=_clock(fixed_now),
    )

    assert result.tags_source == current_tags.resolve()
    assert json.loads(app_paths.custom_tags.read_text(encoding="utf-8")) == ["过渡标签"]


def test_multiple_tag_candidates_are_not_guessed(
    app_paths: AppPaths,
    worktree_root: Path,
    tmp_path: Path,
    fixed_now,
) -> None:
    configured = tmp_path / "configured-tags.json"
    current_tags = (
        worktree_root
        / "pc-app-build"
        / "apps"
        / "notes-pyside"
        / "app"
        / "data"
        / "custom_tags.json"
    )
    configured.write_text('["客户"]', encoding="utf-8")
    current_tags.parent.mkdir(parents=True, exist_ok=True)
    current_tags.write_text('["跟进"]', encoding="utf-8")

    with pytest.raises(MigrationConflictError) as captured:
        prepare_gate1_local_data(
            app_paths,
            worktree_root=worktree_root,
            env={LEGACY_TAGS_ENV: str(configured)},
            now_provider=_clock(fixed_now),
        )

    assert captured.value.kind == "tag file"
    assert not app_paths.custom_tags.exists()
