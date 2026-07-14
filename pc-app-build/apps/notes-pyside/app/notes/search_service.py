"""
LIKE-based fuzzy search for notes.

Phase 2 intentionally uses simple SQLite LIKE matching. Future phases can replace
or extend this module with FTS5, Chinese segmentation, embeddings, or hybrid
search without changing API consumers.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Note
from app.schemas import SearchResponse
from app.services.note_service import note_to_read


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def search_notes(
    db: Session,
    *,
    query: str = "",
    limit: int = 10,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    tags: str | None = None,
) -> SearchResponse:
    """Search notes by title, content, and tags using LIKE."""

    normalized_query = query.strip()
    stmt = select(Note).where(Note.is_deleted.is_(False))

    if normalized_query:
        like = f"%{normalized_query}%"
        stmt = stmt.where(
            or_(
                Note.title.like(like),
                Note.content.like(like),
                Note.tags.like(like),
            )
        )

    if date_from is not None:
        stmt = stmt.where(Note.created_at >= date_from)

    if date_to is not None:
        stmt = stmt.where(Note.created_at <= date_to)

    for tag in _split_csv(tags):
        stmt = stmt.where(Note.tags.like(f"%{tag}%"))

    stmt = stmt.order_by(Note.is_pinned.desc(), Note.updated_at.desc(), Note.id.desc()).limit(limit)

    notes = db.execute(stmt).scalars().all()
    items = [note_to_read(note) for note in notes]

    return SearchResponse(
        query=normalized_query,
        total=len(items),
        items=items,
    )
