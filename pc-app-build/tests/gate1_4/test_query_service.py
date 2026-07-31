from __future__ import annotations

import os
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

APP_ROOT = Path(__file__).resolve().parents[2] / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.notes import (  # noqa: E402
    Note,
    NoteQueryService,
    NoteRepositoryError,
    NoteServiceRepositoryError,
    NoteSource,
)


def make_sample_note() -> Note:
    timestamp = datetime(2026, 7, 14, 8, 0, tzinfo=timezone.utc)
    return Note(
        id=1,
        title="sample",
        content="content",
        tags=("客户",),
        is_pinned=False,
        is_deleted=False,
        created_at=timestamp,
        updated_at=timestamp,
        source=NoteSource.MANUAL,
    )


class RecordingExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, tuple[Any, ...], dict[str, Any]]] = []

    async def run(self, operation, /, *args, **kwargs):
        self.calls.append((operation, args, kwargs))
        return operation(*args, **kwargs)


class StubRepository:
    def __init__(self, note) -> None:
        self.note = note
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def list_active(self):
        self.calls.append(("list_active", ()))
        return (self.note,)

    def list_pinned(self):
        self.calls.append(("list_pinned", ()))
        return (self.note,)

    def list_deleted(self):
        self.calls.append(("list_deleted", ()))
        return ()

    def list_by_tag(self, tag):
        self.calls.append(("list_by_tag", (tag,)))
        return (self.note,)

    def search(self, query, limit=100):
        self.calls.append(("search", (query, limit)))
        return (self.note,)

    def get(self, note_id, include_deleted=False):
        self.calls.append(("get", (note_id, include_deleted)))
        return self.note


@pytest.mark.asyncio
async def test_each_query_enters_executor_once() -> None:
    sample_note = make_sample_note()
    repository = StubRepository(sample_note)
    executor = RecordingExecutor()
    service = NoteQueryService(repository, executor)

    assert await service.list_all() == (sample_note,)
    assert await service.list_pinned() == (sample_note,)
    assert await service.list_deleted() == ()
    assert await service.list_by_tag("客户") == (sample_note,)
    assert await service.search("sample", 25) == (sample_note,)
    assert await service.get(1, include_deleted=True) == sample_note

    assert len(executor.calls) == 6
    assert repository.calls == [
        ("list_active", ()),
        ("list_pinned", ()),
        ("list_deleted", ()),
        ("list_by_tag", ("客户",)),
        ("search", ("sample", 25)),
        ("get", (1, True)),
    ]


@pytest.mark.asyncio
async def test_generic_repository_error_is_mapped() -> None:
    class BrokenRepository(StubRepository):
        def list_active(self):
            raise NoteRepositoryError("storage failed")

    service = NoteQueryService(BrokenRepository(make_sample_note()), RecordingExecutor())

    with pytest.raises(NoteServiceRepositoryError) as captured:
        await service.list_all()

    assert captured.value.operation == "list_all"
    assert captured.value.code == "note_repository_error"
    assert isinstance(captured.value.cause, NoteRepositoryError)


@pytest.mark.asyncio
async def test_conversational_search_prefers_exact_tag_over_body_match() -> None:
    customer_note = make_sample_note()
    body_only_note = replace(
        customer_note,
        id=2,
        title="屏幕样机",
        content="完成后发给客户",
        tags=("屏幕",),
    )

    class MultipleRepository(StubRepository):
        def list_active(self):
            self.calls.append(("list_active", ()))
            return (customer_note, body_only_note)

    service = NoteQueryService(
        MultipleRepository(customer_note),
        RecordingExecutor(),
    )

    results = await service.search_terms_filtered(
        ("客户相关", "客户"),
        limit=10,
    )

    assert results == (customer_note,)


@pytest.mark.asyncio
async def test_conversational_search_falls_back_to_full_text_without_exact_tag() -> None:
    customer_note = make_sample_note()
    manager_note = replace(
        customer_note,
        id=2,
        title="联系王总",
        content="确认报价",
        tags=("跟进",),
    )

    class MultipleRepository(StubRepository):
        def list_active(self):
            self.calls.append(("list_active", ()))
            return (customer_note, manager_note)

    service = NoteQueryService(
        MultipleRepository(customer_note),
        RecordingExecutor(),
    )

    results = await service.search_terms_filtered(
        ("王总相关", "王总"),
        limit=10,
    )

    assert results == (manager_note,)
