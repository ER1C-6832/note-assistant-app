"""Serialized application boundary for shared UI and MCP tag catalog access."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterable
from dataclasses import dataclass

from .query_service import NoteQueryService
from .tag_catalog import (
    PROTECTED_TAGS,
    SYSTEM_CATEGORY_NAMES,
    TagCatalog,
    TagCatalogItem,
    TagInUseError,
    TagValidationError,
)


@dataclass(frozen=True, slots=True)
class TagDeleteInspection:
    name: str
    exists: bool
    protected: bool
    system: bool
    in_use: bool
    deletable: bool


class TagCatalogService:
    """Serialize all catalog writes and expose a UI-compatible facade.

    The synchronous methods keep the existing NotesViewModel contract. MCP and
    other async callers use the ``*_async`` methods. Both paths share the same
    re-entrant lock, preventing lost updates to the JSON catalog.
    """

    def __init__(self, catalog: TagCatalog, queries: NoteQueryService) -> None:
        self._catalog = catalog
        self._queries = queries
        self._lock = threading.RLock()
        self._closed = False

    @property
    def path(self):
        return self._catalog.path

    @property
    def protected_tags(self) -> frozenset[str]:
        return self._catalog.protected_tags

    @property
    def custom_tags(self) -> tuple[str, ...]:
        with self._lock:
            self._ensure_open()
            return self._catalog.custom_tags

    def load(self) -> tuple[str, ...]:
        with self._lock:
            self._ensure_open()
            return self._catalog.load()

    def add(self, tag: str) -> bool:
        with self._lock:
            self._ensure_open()
            return self._catalog.add(tag)

    def observe(self, tags: Iterable[str]) -> tuple[str, ...]:
        with self._lock:
            self._ensure_open()
            return self._catalog.observe(tags)

    def delete(self, tag: str, *, used_tags: Iterable[str]) -> bool:
        with self._lock:
            self._ensure_open()
            return self._catalog.delete(tag, used_tags=used_tags)

    def is_deletable(self, tag: str, *, used_tags: Iterable[str]) -> bool:
        with self._lock:
            self._ensure_open()
            return self._catalog.is_deletable(tag, used_tags=used_tags)

    def items(self, *, used_tags: Iterable[str]) -> tuple[TagCatalogItem, ...]:
        with self._lock:
            self._ensure_open()
            return self._catalog.items(used_tags=used_tags)

    async def add_async(self, tag: str) -> bool:
        return await asyncio.to_thread(self.add, tag)

    async def observe_async(self, tags: Iterable[str]) -> tuple[str, ...]:
        frozen = tuple(tags)
        return await asyncio.to_thread(self.observe, frozen)

    async def delete_async(self, tag: str) -> bool:
        used = await self._used_tags()
        return await asyncio.to_thread(self.delete, tag, used_tags=used)

    async def inspect_delete(self, tag: str) -> TagDeleteInspection:
        name = str(tag).strip()
        if not name:
            raise TagValidationError("tag must not be empty")
        active, deleted = await asyncio.gather(
            self._queries.list_all(), self._queries.list_deleted()
        )
        used = {value for note in (*active, *deleted) for value in note.tags}
        with self._lock:
            self._ensure_open()
            custom = set(self._catalog.custom_tags)
            protected = name in self._catalog.protected_tags
            system = name in SYSTEM_CATEGORY_NAMES
            in_use = name in used
            exists = name in custom or protected or in_use
            deletable = name in custom and not protected and not system and not in_use
        return TagDeleteInspection(name, exists, protected, system, in_use, deletable)

    async def list_public(self, *, include_usage: bool = True) -> tuple[dict[str, object], ...]:
        used = await self._used_tags() if include_usage else set()
        with self._lock:
            self._ensure_open()
            custom_items = self._catalog.items(used_tags=used)
            result = [
                {
                    "name": item.name,
                    "protected": item.protected,
                    "in_use": item.in_use,
                    "deletable": item.deletable,
                }
                for item in custom_items
            ]
            known = {item["name"] for item in result}
            for name in sorted(used):
                if (
                    name not in known
                    and name not in PROTECTED_TAGS
                    and name not in SYSTEM_CATEGORY_NAMES
                ):
                    result.append(
                        {
                            "name": name,
                            "protected": False,
                            "in_use": True,
                            "deletable": False,
                        }
                    )
                    known.add(name)
            for name in sorted(PROTECTED_TAGS):
                if name not in known:
                    result.append(
                        {
                            "name": name,
                            "protected": True,
                            "in_use": name in used,
                            "deletable": False,
                        }
                    )
        return tuple(result)

    async def search_public(self, query: str, *, limit: int = 10) -> tuple[dict[str, object], ...]:
        clean = str(query).strip().casefold()
        safe_limit = max(1, min(int(limit), 10))
        items = await self.list_public(include_usage=True)
        return tuple(item for item in items if clean in str(item["name"]).casefold())[:safe_limit]

    async def close(self) -> None:
        with self._lock:
            self._closed = True

    async def _used_tags(self) -> set[str]:
        active, deleted = await asyncio.gather(
            self._queries.list_all(), self._queries.list_deleted()
        )
        return {value for note in (*active, *deleted) for value in note.tags}

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("tag catalog service is closed")


__all__ = [
    "TagCatalogService",
    "TagDeleteInspection",
    "TagInUseError",
    "TagValidationError",
]
