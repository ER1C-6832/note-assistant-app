"""
Application state placeholder for Phase 3.

Phase 3 keeps page navigation in QML for fast UI iteration. Later phases can
move state, Notes API calls, and Sidecar event handling into Python controllers.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AppState:
    """Minimal app state container."""

    current_page: str = "home"
    selected_note_id: int | None = None
    search_keyword: str = ""
