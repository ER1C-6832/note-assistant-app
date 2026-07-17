"""Asynchronous note mutation boundary shared by UI and MCP tools."""

from __future__ import annotations

from .commands import (
    BatchUpdateTagsCommand,
    CreateNoteCommand,
    HardDeleteCommand,
    RestoreCommand,
    SetPinnedCommand,
    SoftDeleteCommand,
    UpdateNoteCommand,
)
from .database_executor import DatabaseExecutor
from .domain import Note
from .repository import NoteRepository
from .service_errors import run_repository_call


class NoteCommandService:
    def __init__(self, repository: NoteRepository, executor: DatabaseExecutor) -> None:
        self._repository = repository
        self._executor = executor

    async def create(self, command: CreateNoteCommand) -> Note:
        return await run_repository_call(self._executor, "create", self._repository.create, command)

    async def update(self, command: UpdateNoteCommand) -> Note:
        return await run_repository_call(self._executor, "update", self._repository.update, command)

    async def update_tags(self, command: BatchUpdateTagsCommand) -> tuple[Note, ...]:
        return await run_repository_call(
            self._executor,
            "update_tags",
            self._repository.update_tags_many,
            command,
        )

    async def set_pinned(self, command: SetPinnedCommand) -> tuple[Note, ...]:
        return await run_repository_call(
            self._executor, "set_pinned", self._repository.set_pinned_many, command
        )

    async def soft_delete(self, command: SoftDeleteCommand) -> int:
        return await run_repository_call(
            self._executor, "soft_delete", self._repository.soft_delete_many, command
        )

    async def restore(self, command: RestoreCommand) -> int:
        return await run_repository_call(
            self._executor, "restore", self._repository.restore_many, command
        )

    async def hard_delete(self, command: HardDeleteCommand) -> int:
        return await run_repository_call(
            self._executor, "hard_delete", self._repository.hard_delete_many, command
        )
