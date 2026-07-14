"""Framework-neutral note domain and persistence layer."""

from .commands import (
    CreateNoteCommand,
    HardDeleteCommand,
    NoteValidationError,
    RestoreCommand,
    SetPinnedCommand,
    SoftDeleteCommand,
    UpdateNoteCommand,
)
from .database_executor import DatabaseExecutor, DatabaseExecutorClosedError
from .domain import Note, NoteSource
from .repository import (
    NoteNotFoundError,
    NoteRepository,
    NoteRepositoryError,
    NoteStateError,
)
from .sqlalchemy_repository import (
    SqlAlchemyNoteRepository,
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)

__all__ = [
    "CreateNoteCommand",
    "DatabaseExecutor",
    "DatabaseExecutorClosedError",
    "HardDeleteCommand",
    "Note",
    "NoteNotFoundError",
    "NoteRepository",
    "NoteRepositoryError",
    "NoteSource",
    "NoteStateError",
    "NoteValidationError",
    "RestoreCommand",
    "SetPinnedCommand",
    "SoftDeleteCommand",
    "SqlAlchemyNoteRepository",
    "UpdateNoteCommand",
    "create_session_factory",
    "create_sqlite_engine",
    "initialize_database",
]
