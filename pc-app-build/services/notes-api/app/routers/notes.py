"""
Note CRUD and fuzzy search API routes.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import NoteCreate, NoteDeleteResult, NoteRead, NoteUpdate, SearchResponse
from app.services import note_service
from app.services.search_service import search_notes

router = APIRouter(prefix="/api/notes", tags=["notes"])


@router.post("", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
async def create_note(payload: NoteCreate, db: Session = Depends(get_db)) -> NoteRead:
    """Create a note."""

    return note_service.create_note(db, payload)


@router.get("", response_model=list[NoteRead])
async def list_notes(
    include_deleted: bool = Query(False),
    tag: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[NoteRead]:
    """List notes."""

    return note_service.list_notes(
        db,
        include_deleted=include_deleted,
        tag=tag,
        limit=limit,
        offset=offset,
    )


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query("", description="Keyword for fuzzy search"),
    limit: int = Query(10, ge=1, le=100),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    tags: str | None = Query(None, description="Comma-separated tag filters"),
    db: Session = Depends(get_db),
) -> SearchResponse:
    """Fuzzy search notes by title, content, and tags."""

    return search_notes(
        db,
        query=q,
        limit=limit,
        date_from=date_from,
        date_to=date_to,
        tags=tags,
    )


@router.get("/{note_id}", response_model=NoteRead)
async def get_note(
    note_id: int,
    include_deleted: bool = Query(False),
    db: Session = Depends(get_db),
) -> NoteRead:
    """Get a note by ID."""

    note = note_service.get_note(db, note_id, include_deleted=include_deleted)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


@router.patch("/{note_id}", response_model=NoteRead)
async def update_note(
    note_id: int,
    payload: NoteUpdate,
    db: Session = Depends(get_db),
) -> NoteRead:
    """Update a note by ID."""

    note = note_service.update_note(db, note_id, payload)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


@router.delete("/{note_id}", response_model=NoteDeleteResult)
async def delete_note(note_id: int, db: Session = Depends(get_db)) -> NoteDeleteResult:
    """Soft-delete a note by ID."""

    note = note_service.soft_delete_note(db, note_id)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    return NoteDeleteResult(
        success=True,
        note_id=note.id,
        is_deleted=note.is_deleted,
    )


@router.post("/{note_id}/restore", response_model=NoteRead)
async def restore_note(note_id: int, db: Session = Depends(get_db)) -> NoteRead:
    """Restore a soft-deleted note."""

    note = note_service.restore_note(db, note_id)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note
