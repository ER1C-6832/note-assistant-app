from __future__ import annotations

import os
import sys
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
    CreateNoteCommand,
    DatabaseExecutorClosedError,
    HardDeleteCommand,
    Note,
    NoteCommandService,
    NoteNotFoundError,
    NoteServiceNotFoundError,
    NoteServiceStateError,
    NoteServiceUnavailableError,
    NoteSource,
    NoteStateError,
    RestoreCommand,
    SetPinnedCommand,
    SoftDeleteCommand,
    UpdateNoteCommand,
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


class ClosedExecutor:
    async def run(self, operation, /, *args, **kwargs):
        raise DatabaseExecutorClosedError("closed")


class StubRepository:
    def __init__(self, note) -> None:
        self.note = note
        self.calls: list[tuple[str, Any]] = []

    def create(self, command):
        self.calls.append(("create", command))
        return self.note

    def update(self, command):
        self.calls.append(("update", command))
        return self.note

    def set_pinned_many(self, command):
        self.calls.append(("set_pinned_many", command))
        return (self.note,)

    def soft_delete_many(self, command):
        self.calls.append(("soft_delete_many", command))
        return len(command.note_ids)

    def restore_many(self, command):
        self.calls.append(("restore_many", command))
        return len(command.note_ids)

    def hard_delete_many(self, command):
        self.calls.append(("hard_delete_many", command))
        return len(command.note_ids)


@pytest.mark.asyncio
async def test_each_command_enters_executor_once() -> None:
    sample_note = make_sample_note()
    repository = StubRepository(sample_note)
    executor = RecordingExecutor()
    service = NoteCommandService(repository, executor)

    create = CreateNoteCommand("title", "content", ("客户",))
    update = UpdateNoteCommand(1, "title", "content", ("跟进",))
    pin = SetPinnedCommand((1,), True)
    soft_delete = SoftDeleteCommand((1,))
    restore = RestoreCommand((1,))
    hard_delete = HardDeleteCommand((1,))

    assert await service.create(create) == sample_note
    assert await service.update(update) == sample_note
    assert await service.set_pinned(pin) == (sample_note,)
    assert await service.soft_delete(soft_delete) == 1
    assert await service.restore(restore) == 1
    assert await service.hard_delete(hard_delete) == 1

    assert len(executor.calls) == 6
    assert [name for name, _ in repository.calls] == [
        "create",
        "update",
        "set_pinned_many",
        "soft_delete_many",
        "restore_many",
        "hard_delete_many",
    ]


@pytest.mark.asyncio
async def test_not_found_error_is_mapped() -> None:
    sample_note = make_sample_note()

    class MissingRepository(StubRepository):
        def update(self, command):
            raise NoteNotFoundError((command.note_id,))

    service = NoteCommandService(MissingRepository(sample_note), RecordingExecutor())

    with pytest.raises(NoteServiceNotFoundError) as captured:
        await service.update(UpdateNoteCommand(7, "title", "content", ()))

    assert captured.value.operation == "update"
    assert captured.value.missing_ids == (7,)
    assert captured.value.code == "note_not_found"


@pytest.mark.asyncio
async def test_invalid_state_error_is_mapped() -> None:
    sample_note = make_sample_note()

    class InvalidStateRepository(StubRepository):
        def restore_many(self, command):
            raise NoteStateError(command.note_ids, "deleted")

    service = NoteCommandService(
        InvalidStateRepository(sample_note),
        RecordingExecutor(),
    )

    with pytest.raises(NoteServiceStateError) as captured:
        await service.restore(RestoreCommand((1, 2)))

    assert captured.value.operation == "restore"
    assert captured.value.invalid_ids == (1, 2)
    assert captured.value.expected_state == "deleted"


@pytest.mark.asyncio
async def test_closed_executor_is_mapped() -> None:
    service = NoteCommandService(StubRepository(make_sample_note()), ClosedExecutor())

    with pytest.raises(NoteServiceUnavailableError) as captured:
        await service.create(CreateNoteCommand("title", "content", ()))

    assert captured.value.operation == "create"
    assert captured.value.code == "note_service_unavailable"
