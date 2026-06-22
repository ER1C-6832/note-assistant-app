"""
Note data model for the PC App layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Note:
    id: int
    title: str
    content: str
    tags: list[str]
    is_pinned: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    source: str
