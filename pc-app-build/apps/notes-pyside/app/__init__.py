"""Desktop application package."""

from __future__ import annotations

from .bootstrap import run_application


def run_app() -> int:
    """Start the desktop application."""
    return run_application()


__all__ = ["run_app"]
