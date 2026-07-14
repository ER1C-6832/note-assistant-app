"""Asynchronous note query boundary shared by UI and future MCP tools."""

from __future__ import annotations

from .database_executor import DatabaseExecutor
from .domain import Note
from .repository import NoteRepository
from .service_errors import run_repository_call


class NoteQueryService:
    def __init__(
        self,
        repository: NoteRepository,
        executor: DatabaseExecutor,
    ) -> None:
        self._repository = repository
        self._executor = executor

    async def list_all(self) -> tuple[Note, ...]:
        return await run_repository_call(
            self._executor,
            "list_all",
            self._repository.list_active,
        )

    async def list_pinned(self) -> tuple[Note, ...]:
        return await run_repository_call(
            self._executor,
            "list_pinned",
            self._repository.list_pinned,
        )

    async def list_deleted(self) -> tuple[Note, ...]:
        return await run_repository_call(
            self._executor,
            "list_deleted",
            self._repository.list_deleted,
        )

    async def list_by_tag(self, tag: str) -> tuple[Note, ...]:
        return await run_repository_call(
            self._executor,
            "list_by_tag",
            self._repository.list_by_tag,
            tag,
        )

    async def search(self, query: str, limit: int = 100) -> tuple[Note, ...]:
        return await run_repository_call(
            self._executor,
            "search",
            self._repository.search,
            query,
            limit,
        )

    async def get(
        self,
        note_id: int,
        include_deleted: bool = False,
    ) -> Note | None:
        return await run_repository_call(
            self._executor,
            "get",
            self._repository.get,
            note_id,
            include_deleted,
        )
