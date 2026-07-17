"""SQLite-backed implementation of the note repository contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from sqlalchemy import Engine, Select, create_engine, event, or_, select
from sqlalchemy.orm import Session, sessionmaker

from .commands import (
    CreateNoteCommand,
    HardDeleteCommand,
    RestoreCommand,
    SetPinnedCommand,
    SoftDeleteCommand,
    UpdateNoteCommand,
    normalize_note_id,
)
from .domain import Note, NoteSource, as_utc, utc_now_naive
from .repository import NoteNotFoundError, NoteStateError
from .sqlalchemy_models import Base, NoteRow

SessionFactory = sessionmaker[Session]


def create_sqlite_engine(database_path: str | Path) -> Engine:
    path = Path(database_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite+pysqlite:///{path.as_posix()}",
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=3000")
        finally:
            cursor.close()

    return engine


def create_session_factory(engine: Engine) -> SessionFactory:
    return sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
        future=True,
    )


def initialize_database(engine: Engine) -> None:
    Base.metadata.create_all(bind=engine)


def _serialize_tags(tags: Iterable[str]) -> str:
    return json.dumps(list(tags), ensure_ascii=False, separators=(",", ":"))


def _deserialize_tags(raw_value: str | None) -> tuple[str, ...]:
    if not raw_value:
        return ()
    try:
        value = json.loads(raw_value)
    except (json.JSONDecodeError, TypeError):
        return ()
    if not isinstance(value, list):
        return ()
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        tag = str(item).strip()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        result.append(tag)
    return tuple(result)


def _source_from_storage(value: str) -> NoteSource:
    try:
        return NoteSource(value)
    except ValueError:
        return NoteSource.MANUAL


def _to_domain(row: NoteRow) -> Note:
    return Note(
        id=row.id,
        title=row.title,
        content=row.content,
        tags=_deserialize_tags(row.tags),
        is_pinned=bool(row.is_pinned),
        is_deleted=bool(row.is_deleted),
        created_at=as_utc(row.created_at),
        updated_at=as_utc(row.updated_at),
        source=_source_from_storage(row.source),
    )


def _active_order(statement: Select[tuple[NoteRow]]) -> Select[tuple[NoteRow]]:
    return statement.order_by(
        NoteRow.is_pinned.desc(), NoteRow.updated_at.desc(), NoteRow.id.desc()
    )


class SqlAlchemyNoteRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def create(self, command: CreateNoteCommand) -> Note:
        now = utc_now_naive()
        with self._session_factory() as session, session.begin():
            row = NoteRow(
                title=command.title,
                content=command.content,
                tags=_serialize_tags(command.tags),
                is_pinned=command.is_pinned,
                is_deleted=False,
                created_at=now,
                updated_at=now,
                source=command.source.value,
            )
            session.add(row)
            session.flush()
            result = _to_domain(row)
        return result

    def update(self, command: UpdateNoteCommand) -> Note:
        with self._session_factory() as session, session.begin():
            row = session.execute(
                select(NoteRow).where(
                    NoteRow.id == command.note_id,
                    NoteRow.is_deleted.is_(False),
                )
            ).scalar_one_or_none()
            if row is None:
                raise NoteNotFoundError((command.note_id,))
            row.title = command.title
            row.content = command.content
            row.tags = _serialize_tags(command.tags)
            row.updated_at = utc_now_naive()
            session.flush()
            result = _to_domain(row)
        return result

    def get(self, note_id: int, include_deleted: bool = False) -> Note | None:
        normalized_id = normalize_note_id(note_id)
        statement = select(NoteRow).where(NoteRow.id == normalized_id)
        if not include_deleted:
            statement = statement.where(NoteRow.is_deleted.is_(False))
        with self._session_factory() as session:
            row = session.execute(statement).scalar_one_or_none()
            return _to_domain(row) if row is not None else None

    def list_active(self) -> tuple[Note, ...]:
        statement = _active_order(select(NoteRow).where(NoteRow.is_deleted.is_(False)))
        return self._list(statement)

    def list_recent(self, limit: int = 5) -> tuple[Note, ...]:
        safe_limit = max(1, min(int(limit), 20))
        statement = (
            select(NoteRow)
            .where(NoteRow.is_deleted.is_(False))
            .order_by(NoteRow.updated_at.desc(), NoteRow.id.desc())
            .limit(safe_limit)
        )
        return self._list(statement)

    def list_pinned(self) -> tuple[Note, ...]:
        statement = _active_order(
            select(NoteRow).where(
                NoteRow.is_deleted.is_(False),
                NoteRow.is_pinned.is_(True),
            )
        )
        return self._list(statement)

    def list_deleted(self) -> tuple[Note, ...]:
        statement = (
            select(NoteRow)
            .where(NoteRow.is_deleted.is_(True))
            .order_by(NoteRow.updated_at.desc(), NoteRow.id.desc())
        )
        return self._list(statement)

    def list_by_tag(self, tag: str) -> tuple[Note, ...]:
        clean_tag = str(tag).strip()
        if not clean_tag:
            return ()
        return tuple(note for note in self.list_active() if clean_tag in note.tags)

    def search(self, query: str, limit: int = 100) -> tuple[Note, ...]:
        clean_query = str(query).strip()
        if not clean_query:
            return self.list_active()
        safe_limit = max(1, min(int(limit), 1000))
        pattern = f"%{clean_query}%"
        statement = _active_order(
            select(NoteRow).where(
                NoteRow.is_deleted.is_(False),
                or_(
                    NoteRow.title.like(pattern),
                    NoteRow.content.like(pattern),
                    NoteRow.tags.like(pattern),
                ),
            )
        ).limit(safe_limit)
        return self._list(statement)

    def set_pinned_many(self, command: SetPinnedCommand) -> tuple[Note, ...]:
        with self._session_factory() as session, session.begin():
            rows = self._require_rows(session, command.note_ids, expected_deleted=False)
            now = utc_now_naive()
            for row in rows:
                row.is_pinned = command.is_pinned
                row.updated_at = now
            session.flush()
            by_id = {row.id: _to_domain(row) for row in rows}
            result = tuple(by_id[note_id] for note_id in command.note_ids)
        return result

    def soft_delete_many(self, command: SoftDeleteCommand) -> int:
        with self._session_factory() as session, session.begin():
            rows = self._require_rows(session, command.note_ids, expected_deleted=False)
            now = utc_now_naive()
            for row in rows:
                row.is_deleted = True
                row.is_pinned = False
                row.updated_at = now
            session.flush()
            count = len(rows)
        return count

    def restore_many(self, command: RestoreCommand) -> int:
        with self._session_factory() as session, session.begin():
            rows = self._require_rows(session, command.note_ids, expected_deleted=True)
            now = utc_now_naive()
            for row in rows:
                row.is_deleted = False
                row.updated_at = now
            session.flush()
            count = len(rows)
        return count

    def hard_delete_many(self, command: HardDeleteCommand) -> int:
        with self._session_factory() as session, session.begin():
            rows = self._require_rows(session, command.note_ids, expected_deleted=True)
            for row in rows:
                session.delete(row)
            session.flush()
            count = len(rows)
        return count

    def _list(self, statement: Select[tuple[NoteRow]]) -> tuple[Note, ...]:
        with self._session_factory() as session:
            rows = session.execute(statement).scalars().all()
            return tuple(_to_domain(row) for row in rows)

    @staticmethod
    def _require_rows(
        session: Session,
        note_ids: tuple[int, ...],
        *,
        expected_deleted: bool,
    ) -> list[NoteRow]:
        rows = session.execute(select(NoteRow).where(NoteRow.id.in_(note_ids))).scalars().all()
        by_id = {row.id: row for row in rows}
        missing = tuple(note_id for note_id in note_ids if note_id not in by_id)
        if missing:
            raise NoteNotFoundError(missing)

        invalid = tuple(
            note_id
            for note_id in note_ids
            if bool(by_id[note_id].is_deleted) is not expected_deleted
        )
        if invalid:
            state = "deleted" if expected_deleted else "active"
            raise NoteStateError(invalid, state)

        return [by_id[note_id] for note_id in note_ids]
