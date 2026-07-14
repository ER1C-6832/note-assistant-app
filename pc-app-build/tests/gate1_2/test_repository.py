from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from app.notes import (
    CreateNoteCommand,
    HardDeleteCommand,
    NoteNotFoundError,
    NoteSource,
    NoteStateError,
    RestoreCommand,
    SetPinnedCommand,
    SoftDeleteCommand,
    SqlAlchemyNoteRepository,
    UpdateNoteCommand,
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)


def create(repo, title: str, *, tags=(), pinned=False, source=NoteSource.MANUAL):
    return repo.create(
        CreateNoteCommand(
            title=title,
            content=f"content-{title}",
            tags=tuple(tags),
            is_pinned=pinned,
            source=source,
        )
    )


def test_crud_and_source_preservation(repository) -> None:
    created = create(repository, "first", tags=("客户",), source=NoteSource.VOICE_PC)
    assert created.id > 0
    assert created.source is NoteSource.VOICE_PC
    assert created.created_at.tzinfo is timezone.utc

    loaded = repository.get(created.id)
    assert loaded == created

    updated = repository.update(
        UpdateNoteCommand(
            note_id=created.id,
            title="updated",
            content="body",
            tags=("跟进",),
        )
    )
    assert updated.title == "updated"
    assert updated.tags == ("跟进",)
    assert updated.source is NoteSource.VOICE_PC


def test_active_pinned_deleted_and_restore(repository) -> None:
    first = create(repository, "first")
    second = create(repository, "second", pinned=True)

    assert [note.id for note in repository.list_active()] == [second.id, first.id]
    assert [note.id for note in repository.list_pinned()] == [second.id]

    assert repository.soft_delete_many(SoftDeleteCommand((second.id,))) == 1
    assert repository.get(second.id) is None
    assert repository.get(second.id, include_deleted=True).is_deleted is True
    assert [note.id for note in repository.list_deleted()] == [second.id]

    assert repository.restore_many(RestoreCommand((second.id,))) == 1
    assert repository.get(second.id).is_deleted is False


def test_hard_delete_requires_deleted_state(repository) -> None:
    note = create(repository, "first")
    with pytest.raises(NoteStateError):
        repository.hard_delete_many(HardDeleteCommand((note.id,)))

    repository.soft_delete_many(SoftDeleteCommand((note.id,)))
    assert repository.hard_delete_many(HardDeleteCommand((note.id,))) == 1
    assert repository.get(note.id, include_deleted=True) is None


def test_exact_tag_matching(repository) -> None:
    exact = create(repository, "exact", tags=("客户",))
    create(repository, "similar", tags=("客户服务",))
    assert [note.id for note in repository.list_by_tag("客户")] == [exact.id]


def test_search_title_content_and_tags(repository) -> None:
    title = create(repository, "Alpha")
    content = repository.create(CreateNoteCommand("Other", "needle", (), False))
    tagged = create(repository, "Tagged", tags=("标签词",))
    deleted = create(repository, "Alpha deleted")
    repository.soft_delete_many(SoftDeleteCommand((deleted.id,)))

    assert title.id in {note.id for note in repository.search("Alpha")}
    assert content.id in {note.id for note in repository.search("needle")}
    assert tagged.id in {note.id for note in repository.search("标签词")}
    assert deleted.id not in {note.id for note in repository.search("Alpha")}


def test_bulk_pin_is_atomic_when_id_is_missing(repository) -> None:
    first = create(repository, "first")
    second = create(repository, "second")

    with pytest.raises(NoteNotFoundError):
        repository.set_pinned_many(SetPinnedCommand((first.id, 999999, second.id), True))

    assert repository.get(first.id).is_pinned is False
    assert repository.get(second.id).is_pinned is False


def test_bulk_soft_delete_is_atomic_when_state_is_invalid(repository) -> None:
    first = create(repository, "first")
    second = create(repository, "second")
    repository.soft_delete_many(SoftDeleteCommand((second.id,)))

    with pytest.raises(NoteStateError):
        repository.soft_delete_many(SoftDeleteCommand((first.id, second.id)))

    assert repository.get(first.id).is_deleted is False
    assert repository.get(second.id, include_deleted=True).is_deleted is True


def test_sorting_uses_pin_updated_and_id(repository) -> None:
    older = create(repository, "older")
    newer = create(repository, "newer")
    repository.set_pinned_many(SetPinnedCommand((older.id,), True))
    assert [note.id for note in repository.list_active()][0] == older.id
    assert newer.id in [note.id for note in repository.list_active()]


def test_legacy_naive_utc_is_exposed_as_aware_utc(tmp_path) -> None:
    database = tmp_path / "legacy.db"
    connection = sqlite3.connect(database)
    connection.execute("""
        CREATE TABLE notes (
            id INTEGER PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            content TEXT NOT NULL,
            tags TEXT NOT NULL DEFAULT '[]',
            is_pinned BOOLEAN NOT NULL DEFAULT 0,
            is_deleted BOOLEAN NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            source VARCHAR(50) NOT NULL DEFAULT 'manual'
        )
        """)
    connection.execute("""
        INSERT INTO notes
        (id, title, content, tags, is_pinned, is_deleted, created_at, updated_at, source)
        VALUES (1, 'legacy', '', '[]', 0, 0, '2024-01-01 12:00:00', '2024-01-02 12:00:00', 'manual')
        """)
    connection.commit()
    connection.close()

    engine = create_sqlite_engine(database)
    initialize_database(engine)
    repo = SqlAlchemyNoteRepository(create_session_factory(engine))
    try:
        note = repo.get(1)
        assert note is not None
        assert note.created_at == datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        assert note.updated_at == datetime(2024, 1, 2, 12, 0, tzinfo=timezone.utc)
    finally:
        engine.dispose()


def test_sqlite_pragmas_are_configured(tmp_path) -> None:
    engine = create_sqlite_engine(tmp_path / "pragma.db")
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA journal_mode").scalar_one().lower() == "wal"
            assert connection.exec_driver_sql("PRAGMA synchronous").scalar_one() == 1
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() == 3000
    finally:
        engine.dispose()
