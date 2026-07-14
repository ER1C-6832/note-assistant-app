"""Synchronous repository contract used inside the database executor."""

from __future__ import annotations

from typing import Protocol

from .commands import (
    CreateNoteCommand,
    HardDeleteCommand,
    RestoreCommand,
    SetPinnedCommand,
    SoftDeleteCommand,
    UpdateNoteCommand,
)
from .domain import Note


class NoteRepositoryError(RuntimeError):
    pass


class NoteNotFoundError(NoteRepositoryError):
    def __init__(self, missing_ids: tuple[int, ...]) -> None:
        self.missing_ids = missing_ids
        super().__init__(f"notes not found: {missing_ids}")


class NoteStateError(NoteRepositoryError):
    def __init__(self, invalid_ids: tuple[int, ...], expected_state: str) -> None:
        self.invalid_ids = invalid_ids
        self.expected_state = expected_state
        super().__init__(
            f"notes {invalid_ids} are not in expected state: {expected_state}"
        )


class NoteRepository(Protocol):
    def create(self, command: CreateNoteCommand) -> Note: ...

    def update(self, command: UpdateNoteCommand) -> Note: ...

    def get(self, note_id: int, include_deleted: bool = False) -> Note | None: ...

    def list_active(self) -> tuple[Note, ...]: ...

    def list_pinned(self) -> tuple[Note, ...]: ...

    def list_deleted(self) -> tuple[Note, ...]: ...

    def list_by_tag(self, tag: str) -> tuple[Note, ...]: ...

    def search(self, query: str, limit: int = 100) -> tuple[Note, ...]: ...

    def set_pinned_many(self, command: SetPinnedCommand) -> tuple[Note, ...]: ...

    def soft_delete_many(self, command: SoftDeleteCommand) -> int: ...

    def restore_many(self, command: RestoreCommand) -> int: ...

    def hard_delete_many(self, command: HardDeleteCommand) -> int: ...
