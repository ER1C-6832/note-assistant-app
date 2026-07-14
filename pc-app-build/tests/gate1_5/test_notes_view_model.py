from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.notes import Note, NoteSource, TagCatalog
from app.ui.note_list_model import NoteListModel
from app.ui.notes_view_model import NotesViewModel


def make_note(note_id: int, *, title: str | None = None, pinned: bool = False) -> Note:
    now = datetime(2026, 7, 14, 12, 30, tzinfo=timezone.utc)
    return Note(
        id=note_id,
        title=title or f"note-{note_id}",
        content=f"content-{note_id}",
        tags=("客户",),
        is_pinned=pinned,
        is_deleted=False,
        created_at=now,
        updated_at=now,
        source=NoteSource.MANUAL,
    )


class FakeQueryService:
    def __init__(self) -> None:
        self.active = (make_note(1), make_note(2))
        self.pinned = (make_note(3, pinned=True),)
        self.deleted = ()

    async def list_all(self):
        return self.active

    async def list_pinned(self):
        return self.pinned

    async def list_deleted(self):
        return self.deleted

    async def list_by_tag(self, _tag):
        return self.active

    async def search(self, _query, limit=100):
        return self.active[:limit]


class FakeCommandService:
    def __init__(self) -> None:
        self.create_calls = []
        self.create_release = asyncio.Event()
        self.created = make_note(9)

    async def create(self, command):
        self.create_calls.append(command)
        await self.create_release.wait()
        return self.created

    async def update(self, command):
        return make_note(command.note_id, title=command.title)

    async def set_pinned(self, command):
        return tuple(make_note(note_id, pinned=command.is_pinned) for note_id in command.note_ids)

    async def soft_delete(self, command):
        return len(command.note_ids)

    async def restore(self, command):
        return len(command.note_ids)

    async def hard_delete(self, command):
        return len(command.note_ids)


def make_view_model(tmp_path: Path, query=None, command=None):
    catalog = TagCatalog(tmp_path / "custom_tags.json", default_tags=())
    catalog.load()
    return NotesViewModel(
        command or FakeCommandService(),
        query or FakeQueryService(),
        catalog,
        NoteListModel(),
        NoteListModel(),
    )


async def settle() -> None:
    for _ in range(20):
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_selection_survives_refresh_by_note_id(tmp_path: Path) -> None:
    query = FakeQueryService()
    vm = make_view_model(tmp_path, query=query)

    vm.loadAll()
    await settle()
    vm.selectNote(1)
    assert vm.selectedTitle == "note-2"

    query.active = (make_note(2, title="note-2-updated"), make_note(1))
    vm.refreshCurrentView()
    await settle()

    assert vm.selectedIndex == 0
    assert vm.selectedTitle == "note-2-updated"
    await vm.close()


@pytest.mark.asyncio
async def test_new_query_cannot_be_overwritten_by_stale_result(tmp_path: Path) -> None:
    release = asyncio.Event()

    class StaleQueryService(FakeQueryService):
        async def list_all(self):
            try:
                await release.wait()
            except asyncio.CancelledError:
                await asyncio.sleep(0)
            return (make_note(1, title="stale"),)

    query = StaleQueryService()
    vm = make_view_model(tmp_path, query=query)

    vm.loadAll()
    await asyncio.sleep(0)
    vm.loadCategory("pinned")
    release.set()
    await settle()

    assert vm.activeCategory == "pinned"
    assert vm.resultCount == 1
    assert vm.selectedTitle == "note-3"
    await vm.close()


@pytest.mark.asyncio
async def test_mutations_are_serialized_and_signal_after_success(tmp_path: Path) -> None:
    command = FakeCommandService()
    vm = make_view_model(tmp_path, command=command)
    failures = []
    created = []
    vm.operationFailed.connect(lambda operation, message: failures.append((operation, message)))
    vm.noteCreated.connect(created.append)

    vm.requestCreateNote("first", "body", "客户", False)
    await asyncio.sleep(0)
    vm.requestCreateNote("second", "body", "客户", False)

    assert vm.mutationBusy is True
    assert len(command.create_calls) == 1
    assert failures and failures[-1][0] == "create"

    command.create_release.set()
    await settle()

    assert created == [9]
    assert vm.mutationBusy is False
    await vm.close()


@pytest.mark.asyncio
async def test_invalid_mutation_is_rejected_without_service_call(tmp_path: Path) -> None:
    command = FakeCommandService()
    vm = make_view_model(tmp_path, command=command)
    failures = []
    vm.operationFailed.connect(lambda operation, message: failures.append((operation, message)))

    vm.requestCreateNote("   ", "body", "", False)
    await settle()

    assert command.create_calls == []
    assert failures and failures[-1][0] == "create"
    assert vm.errorMessage
    await vm.close()
