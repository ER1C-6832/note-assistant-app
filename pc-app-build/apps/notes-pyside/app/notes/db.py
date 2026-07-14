"""Database configuration for local note storage."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base class for SQLAlchemy ORM models."""


_SERVICE_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DB_PATH = _SERVICE_ROOT / "data" / "notes.db"


def get_database_url() -> str:
    """Return the SQLAlchemy database URL.

    NOTES_DB_PATH may be either an absolute path or a path relative to the
    app package root.
    """

    raw_path = os.getenv("NOTES_DB_PATH", str(_DEFAULT_DB_PATH))
    db_path = Path(raw_path)

    if not db_path.is_absolute():
        db_path = _SERVICE_ROOT / db_path

    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path.as_posix()}"


engine = create_engine(
    get_database_url(),
    connect_args={"check_same_thread": False},
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


def init_db() -> None:
    """Create database tables if they do not already exist."""

    # Import models here so metadata is populated before create_all.
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
