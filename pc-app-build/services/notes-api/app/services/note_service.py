"""
Business logic for note CRUD operations.
"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Note
from app.schemas import NoteCreate, NoteRead, NoteUpdate


def _serialize_tags(tags: list[str] | None) -> str:
    """Serialize tags as a JSON string for simple SQLite storage."""

    clean_tags = [tag.strip() for tag in (tags or []) if tag and tag.strip()]
    return json.dumps(clean_tags, ensure_ascii=False)


def _deserialize_tags(raw_tags: str | None) -> list[str]:
    """Deserialize a JSON tag list, falling back safely on invalid data."""

    if not raw_tags:
        return []

    try:
        value = json.loads(raw_tags)
    except json.JSONDecodeError:
        return []

    if not isinstance(value, list):
        return []

    return [str(item) for item in value]


def note_to_read(note: Note) -> NoteRead:
    """Convert an ORM model into an API response model."""

    return NoteRead(
        id=note.id,
        title=note.title,
        content=note.content,
        tags=_deserialize_tags(note.tags),
        is_pinned=note.is_pinned,
        is_deleted=note.is_deleted,
        created_at=note.created_at,
        updated_at=note.updated_at,
        source=note.source,
    )


def create_note(db: Session, payload: NoteCreate) -> NoteRead:
    """Create a note."""

    note = Note(
        title=payload.title,
        content=payload.content,
        tags=_serialize_tags(payload.tags),
        is_pinned=payload.is_pinned,
        source=payload.source,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note_to_read(note)


def get_note(db: Session, note_id: int, include_deleted: bool = False) -> NoteRead | None:
    """Return a note by ID."""

    stmt = select(Note).where(Note.id == note_id)
    if not include_deleted:
        stmt = stmt.where(Note.is_deleted.is_(False))

    note = db.execute(stmt).scalar_one_or_none()
    return note_to_read(note) if note else None


def list_notes(
    db: Session,
    *,
    include_deleted: bool = False,
    tag: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[NoteRead]:
    """List notes sorted by pinned state and last update time."""

    stmt = select(Note)

    if not include_deleted:
        stmt = stmt.where(Note.is_deleted.is_(False))

    if tag:
        stmt = stmt.where(Note.tags.like(f"%{tag}%"))

    stmt = (
        stmt.order_by(Note.is_pinned.desc(), Note.updated_at.desc(), Note.id.desc())
        .offset(offset)
        .limit(limit)
    )

    notes = db.execute(stmt).scalars().all()
    return [note_to_read(note) for note in notes]


def update_note(db: Session, note_id: int, payload: NoteUpdate) -> NoteRead | None:
    """Update a note by ID."""

    note = db.execute(
        select(Note).where(Note.id == note_id, Note.is_deleted.is_(False))
    ).scalar_one_or_none()

    if note is None:
        return None

    if payload.title is not None:
        note.title = payload.title

    if payload.content is not None:
        note.content = payload.content

    if payload.tags is not None:
        note.tags = _serialize_tags(payload.tags)

    if payload.is_pinned is not None:
        note.is_pinned = payload.is_pinned

    note.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(note)
    return note_to_read(note)


def soft_delete_note(db: Session, note_id: int) -> Note | None:
    """Soft-delete a note by setting is_deleted = True."""

    note = db.execute(
        select(Note).where(Note.id == note_id, Note.is_deleted.is_(False))
    ).scalar_one_or_none()

    if note is None:
        return None

    note.is_deleted = True
    note.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(note)
    return note


def restore_note(db: Session, note_id: int) -> NoteRead | None:
    """Restore a soft-deleted note."""

    note = db.execute(select(Note).where(Note.id == note_id)).scalar_one_or_none()

    if note is None:
        return None

    note.is_deleted = False
    note.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(note)
    return note_to_read(note)
