"""Validated command objects for note mutations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .domain import NoteSource


class NoteValidationError(ValueError):
    pass


def normalize_title(value: str) -> str:
    title = str(value).strip()
    if not title:
        raise NoteValidationError("title must not be empty")
    if len(title) > 200:
        raise NoteValidationError("title must not exceed 200 characters")
    return title


def normalize_content(value: str) -> str:
    return str(value).rstrip()


def normalize_tags(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        tag = str(value).strip()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        result.append(tag)
    return tuple(result)


def normalize_note_id(value: int) -> int:
    if isinstance(value, bool):
        raise NoteValidationError("note id must be a positive integer")
    try:
        note_id = int(value)
    except (TypeError, ValueError) as exc:
        raise NoteValidationError("note id must be a positive integer") from exc
    if note_id <= 0:
        raise NoteValidationError("note id must be a positive integer")
    return note_id


def normalize_note_ids(values: Iterable[int]) -> tuple[int, ...]:
    result: list[int] = []
    seen: set[int] = set()
    for value in values:
        note_id = normalize_note_id(value)
        if note_id in seen:
            continue
        seen.add(note_id)
        result.append(note_id)
    if not result:
        raise NoteValidationError("at least one note id is required")
    return tuple(result)


def normalize_source(value: NoteSource | str) -> NoteSource:
    if isinstance(value, NoteSource):
        return value
    try:
        return NoteSource(str(value))
    except ValueError as exc:
        raise NoteValidationError(f"unsupported note source: {value!r}") from exc


@dataclass(frozen=True, slots=True)
class CreateNoteCommand:
    title: str
    content: str
    tags: tuple[str, ...]
    is_pinned: bool = False
    source: NoteSource = NoteSource.MANUAL

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", normalize_title(self.title))
        object.__setattr__(self, "content", normalize_content(self.content))
        object.__setattr__(self, "tags", normalize_tags(self.tags))
        object.__setattr__(self, "is_pinned", bool(self.is_pinned))
        object.__setattr__(self, "source", normalize_source(self.source))


@dataclass(frozen=True, slots=True)
class UpdateNoteCommand:
    note_id: int
    title: str
    content: str
    tags: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "note_id", normalize_note_id(self.note_id))
        object.__setattr__(self, "title", normalize_title(self.title))
        object.__setattr__(self, "content", normalize_content(self.content))
        object.__setattr__(self, "tags", normalize_tags(self.tags))


@dataclass(frozen=True, slots=True)
class BatchUpdateTagsCommand:
    note_ids: tuple[int, ...]
    operation: str
    tags: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "note_ids", normalize_note_ids(self.note_ids))
        operation = str(self.operation).strip().lower()
        if operation not in {"add", "remove", "replace"}:
            raise NoteValidationError("unsupported tag binding operation")
        tags = normalize_tags(self.tags)
        if not tags:
            raise NoteValidationError("at least one tag is required")
        object.__setattr__(self, "operation", operation)
        object.__setattr__(self, "tags", tags)


@dataclass(frozen=True, slots=True)
class SetPinnedCommand:
    note_ids: tuple[int, ...]
    is_pinned: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "note_ids", normalize_note_ids(self.note_ids))
        object.__setattr__(self, "is_pinned", bool(self.is_pinned))


@dataclass(frozen=True, slots=True)
class SoftDeleteCommand:
    note_ids: tuple[int, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "note_ids", normalize_note_ids(self.note_ids))


@dataclass(frozen=True, slots=True)
class RestoreCommand:
    note_ids: tuple[int, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "note_ids", normalize_note_ids(self.note_ids))


@dataclass(frozen=True, slots=True)
class HardDeleteCommand:
    note_ids: tuple[int, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "note_ids", normalize_note_ids(self.note_ids))
