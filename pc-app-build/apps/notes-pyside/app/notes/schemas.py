"""
Pydantic schemas for note requests and responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


NoteSource = Literal["manual", "voice_pc", "voice_android", "imported"]


class NoteBase(BaseModel):
    """Shared note fields."""

    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(default="")
    tags: list[str] = Field(default_factory=list)
    is_pinned: bool = False


class NoteCreate(NoteBase):
    """Payload for creating a note."""

    source: NoteSource = "manual"


class NoteUpdate(BaseModel):
    """Payload for updating a note. All fields are optional."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = None
    tags: list[str] | None = None
    is_pinned: bool | None = None


class NoteRead(NoteBase):
    """Response model for a note."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    source: str


class NoteDeleteResult(BaseModel):
    """Response returned after soft-deleting a note."""

    success: bool
    note_id: int
    is_deleted: bool


class SearchResponse(BaseModel):
    """Search result response."""

    query: str
    total: int
    items: list[NoteRead]
