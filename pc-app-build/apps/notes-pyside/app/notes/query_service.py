"""Asynchronous note query boundary shared by UI and MCP tools."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

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

    async def list_recent(self, limit: int = 5) -> tuple[Note, ...]:
        safe_limit = _bounded_limit(limit, maximum=20)
        return await run_repository_call(
            self._executor,
            "list_recent",
            self._repository.list_recent,
            safe_limit,
        )

    async def list_pinned(self) -> tuple[Note, ...]:
        return await run_repository_call(
            self._executor,
            "list_pinned",
            self._repository.list_pinned,
        )

    async def list_pinned_bounded(self, limit: int = 20) -> tuple[Note, ...]:
        notes = await self.list_pinned()
        return notes[: _bounded_limit(limit, maximum=20)]

    async def list_deleted(self) -> tuple[Note, ...]:
        return await run_repository_call(
            self._executor,
            "list_deleted",
            self._repository.list_deleted,
        )

    async def list_deleted_bounded(self, limit: int = 20) -> tuple[Note, ...]:
        notes = await self.list_deleted()
        return notes[: _bounded_limit(limit, maximum=20)]

    async def list_by_tag(self, tag: str) -> tuple[Note, ...]:
        return await run_repository_call(
            self._executor,
            "list_by_tag",
            self._repository.list_by_tag,
            tag,
        )

    async def list_by_tag_bounded(self, tag: str, limit: int = 20) -> tuple[Note, ...]:
        notes = await self.list_by_tag(tag)
        return notes[: _bounded_limit(limit, maximum=20)]

    async def search(self, query: str, limit: int = 100) -> tuple[Note, ...]:
        return await run_repository_call(
            self._executor,
            "search",
            self._repository.search,
            query,
            limit,
        )

    async def search_filtered(
        self,
        query: str,
        *,
        tags: Iterable[str] = (),
        scope: str = "active",
        limit: int = 10,
    ) -> tuple[Note, ...]:
        clean_scope = _scope(scope)
        safe_limit = _bounded_limit(limit, maximum=10)
        clean_tags = tuple(dict.fromkeys(str(tag).strip() for tag in tags if str(tag).strip()))
        clean_query = str(query).strip().casefold()

        if clean_scope == "active":
            candidates = await self.search(query, max(safe_limit * 100, safe_limit))
        elif clean_scope == "deleted":
            candidates = await self.list_deleted()
        else:
            active, deleted = await asyncio.gather(self.list_all(), self.list_deleted())
            candidates = (*active, *deleted)

        filtered = tuple(
            note
            for note in candidates
            if _matches(note, clean_query) and all(tag in note.tags for tag in clean_tags)
        )
        return tuple(
            sorted(filtered, key=lambda note: (note.updated_at, note.id), reverse=True)[:safe_limit]
        )

    async def search_terms_filtered(
        self,
        terms: Iterable[str],
        *,
        tags: Iterable[str] = (),
        scope: str = "active",
        limit: int = 10,
    ) -> tuple[Note, ...]:
        """Search conversational terms while preferring the most precise phrase.

        The first term is the filler-stripped phrase produced by the MCP intent
        normalizer.  If it matches anything, broader fallback tokens are not
        allowed to dilute that precise result set.
        """

        clean_scope = _scope(scope)
        safe_limit = _bounded_limit(limit, maximum=10)
        clean_tags = tuple(dict.fromkeys(str(tag).strip() for tag in tags if str(tag).strip()))
        clean_terms = tuple(
            dict.fromkeys(str(term).strip().casefold() for term in terms if str(term).strip())
        )[:8]
        if not clean_terms:
            return ()

        candidates = await self.list_scope_bounded(clean_scope, 200)
        tagged = tuple(note for note in candidates if all(tag in note.tags for tag in clean_tags))
        exact_tag_term = next(
            (
                term
                for term in clean_terms
                if any(
                    term == note_tag.casefold()
                    for note in tagged
                    for note_tag in note.tags
                )
            ),
            None,
        )
        if exact_tag_term is not None:
            pool = tuple(
                note
                for note in tagged
                if any(
                    exact_tag_term == note_tag.casefold()
                    for note_tag in note.tags
                )
            )
            return tuple(
                sorted(
                    pool,
                    key=lambda note: (note.updated_at, note.id),
                    reverse=True,
                )[:safe_limit]
            )

        primary = clean_terms[0]
        precise = tuple(note for note in tagged if _matches(note, primary))
        pool = precise or tuple(
            note for note in tagged if any(_matches(note, term) for term in clean_terms)
        )
        return tuple(
            sorted(
                pool,
                key=lambda note: (
                    _term_rank(note, clean_terms),
                    note.updated_at,
                    note.id,
                ),
                reverse=True,
            )[:safe_limit]
        )

    async def list_scope_bounded(self, scope: str, limit: int = 100) -> tuple[Note, ...]:
        clean_scope = _scope(scope)
        safe_limit = _bounded_limit(limit, maximum=200)
        if clean_scope == "active":
            notes = await self.list_all()
        elif clean_scope == "deleted":
            notes = await self.list_deleted()
        else:
            active, deleted = await asyncio.gather(self.list_all(), self.list_deleted())
            notes = (*active, *deleted)
        return tuple(
            sorted(notes, key=lambda note: (note.updated_at, note.id), reverse=True)[:safe_limit]
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


def _bounded_limit(value: int, *, maximum: int) -> int:
    return max(1, min(int(value), maximum))


def _scope(value: str) -> str:
    clean = str(value).strip().lower() or "active"
    if clean not in {"active", "deleted", "all"}:
        raise ValueError("invalid note query scope")
    return clean


def _term_rank(note: Note, terms: tuple[str, ...]) -> tuple[int, int, int, int]:
    title = note.title.casefold()
    tags = tuple(tag.casefold() for tag in note.tags)
    matched = tuple(term for term in terms if _matches(note, term))
    exact_title = int(any(title == term for term in matched))
    title_prefix = int(any(title.startswith(term) for term in matched))
    exact_tag = int(any(term in tags for term in matched))
    longest = max((len(term) for term in matched), default=0)
    return len(matched), exact_title + title_prefix + exact_tag, longest, exact_title


def _matches(note: Note, query: str) -> bool:
    if not query:
        return True
    return any(query in str(value).casefold() for value in (note.title, note.content, *note.tags))
