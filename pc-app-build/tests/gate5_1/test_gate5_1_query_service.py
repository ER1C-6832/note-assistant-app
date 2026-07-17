from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.notes import DatabaseExecutor, Note, NoteQueryService, NoteSource


class Repository:
    def __init__(self, notes):
        self.notes = notes
        self.recent_limits = []

    def list_recent(self, limit):
        self.recent_limits.append(limit)
        return tuple(
            sorted(
                (note for note in self.notes if not note.is_deleted),
                key=lambda note: (note.updated_at, note.id),
                reverse=True,
            )[:limit]
        )

    def list_active(self):
        return tuple(note for note in self.notes if not note.is_deleted)

    def list_pinned(self):
        return tuple(note for note in self.notes if note.is_pinned and not note.is_deleted)

    def list_deleted(self):
        return tuple(note for note in self.notes if note.is_deleted)

    def list_by_tag(self, tag):
        return tuple(note for note in self.notes if tag in note.tags and not note.is_deleted)

    def search(self, query, limit=100):
        query = query.casefold()
        return tuple(
            note
            for note in self.notes
            if not note.is_deleted
            and query in " ".join((note.title, note.content, *note.tags)).casefold()
        )[:limit]

    def get(self, note_id, include_deleted=False):
        return next(
            (
                note
                for note in self.notes
                if note.id == note_id and (include_deleted or not note.is_deleted)
            ),
            None,
        )


def _notes():
    now = datetime.now(timezone.utc)
    return (
        Note(
            1,
            "旧置顶",
            "",
            (),
            True,
            False,
            now,
            now - timedelta(days=2),
            NoteSource.MANUAL,
        ),
        Note(2, "最新", "keyword", ("工作",), False, False, now, now, NoteSource.MANUAL),
        Note(3, "已删除", "keyword", ("工作",), False, True, now, now, NoteSource.MANUAL),
    )


@pytest.mark.asyncio
async def test_recent_is_real_updated_order_not_pinned_first() -> None:
    executor = DatabaseExecutor()
    repository = Repository(_notes())
    service = NoteQueryService(repository, executor)
    try:
        notes = await service.list_recent(5)
        assert [note.id for note in notes] == [2, 1]
        assert repository.recent_limits == [5]
    finally:
        await executor.close()


@pytest.mark.asyncio
async def test_filtered_search_respects_scope_tags_and_limit() -> None:
    executor = DatabaseExecutor()
    service = NoteQueryService(Repository(_notes()), executor)
    try:
        active = await service.search_filtered("keyword", tags=("工作",), scope="active", limit=10)
        deleted = await service.search_filtered(
            "keyword", tags=("工作",), scope="deleted", limit=10
        )
        assert [note.id for note in active] == [2]
        assert [note.id for note in deleted] == [3]
    finally:
        await executor.close()
