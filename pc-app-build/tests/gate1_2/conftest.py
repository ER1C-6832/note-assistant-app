from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[2] / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.notes import (  # noqa: E402
    SqlAlchemyNoteRepository,
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)


@pytest.fixture
def repository(tmp_path):
    engine = create_sqlite_engine(tmp_path / "notes.db")
    initialize_database(engine)
    repo = SqlAlchemyNoteRepository(create_session_factory(engine))
    try:
        yield repo
    finally:
        engine.dispose()
