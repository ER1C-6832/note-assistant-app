"""Framework-neutral note domain objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

try:
    from enum import StrEnum
except ImportError:  # Python 3.10 compatibility

    class StrEnum(str, Enum):
        pass


class NoteSource(StrEnum):
    MANUAL = "manual"
    VOICE_PC = "voice_pc"
    VOICE_ANDROID = "voice_android"
    IMPORTED = "imported"


@dataclass(frozen=True, slots=True)
class Note:
    id: int
    title: str
    content: str
    tags: tuple[str, ...]
    is_pinned: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    source: NoteSource

    def __post_init__(self) -> None:
        if self.id <= 0:
            raise ValueError("note id must be a positive integer")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("domain datetimes must be timezone-aware")


def as_utc(value: datetime) -> datetime:
    """Interpret legacy naive values as UTC and normalize aware values to UTC."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_naive() -> datetime:
    """Return naive UTC for compatibility with the existing SQLite schema."""

    return utc_now().replace(tzinfo=None)
