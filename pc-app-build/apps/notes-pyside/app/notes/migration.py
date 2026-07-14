"""Safe first-run migration of legacy note data into the local application directory."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.app_paths import AppPaths

from .sqlalchemy_repository import create_sqlite_engine, initialize_database

LEGACY_DB_ENV = "NOTE_ASSISTANT_LEGACY_DB_PATH"
LEGACY_TAGS_ENV = "NOTE_ASSISTANT_LEGACY_TAGS_PATH"
MIGRATION_REPORT_NAME = "migration-gate1.json"
REQUIRED_NOTE_COLUMNS = frozenset(
    {
        "id",
        "title",
        "content",
        "tags",
        "is_pinned",
        "is_deleted",
        "created_at",
        "updated_at",
        "source",
    }
)
_SUCCESS_STATUSES = frozenset({"created_empty", "migrated", "existing"})


class DataPreparationError(RuntimeError):
    """Base class for migration and first-run data validation failures."""


class MigrationConflictError(DataPreparationError):
    def __init__(self, kind: str, candidates: Sequence[Path]) -> None:
        self.kind = kind
        self.candidates = tuple(candidates)
        paths = ", ".join(str(path) for path in self.candidates)
        super().__init__(f"multiple {kind} migration candidates found: {paths}")


class DatabaseValidationError(DataPreparationError):
    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"invalid SQLite database {path}: {reason}")


class LegacySchemaError(DatabaseValidationError):
    def __init__(self, path: Path, missing_columns: Sequence[str]) -> None:
        self.missing_columns = tuple(missing_columns)
        super().__init__(path, f"notes table is missing columns: {self.missing_columns}")


class TagFileValidationError(DataPreparationError):
    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"invalid tag file {path}: {reason}")


@dataclass(frozen=True, slots=True)
class LegacyCandidate:
    label: str
    path: Path


@dataclass(frozen=True, slots=True)
class DatabaseInspection:
    path: Path
    quick_check: str
    columns: frozenset[str]
    notes_count: int


@dataclass(frozen=True, slots=True)
class MigrationResult:
    status: str
    source_db: Path | None
    target_db: Path
    backup_db: Path | None
    tags_source: Path | None
    notes_count: int
    report_path: Path


@dataclass(frozen=True, slots=True)
class MigrationReport:
    started_at: str
    finished_at: str
    source_db: str | None
    target_db: str
    source_size: int | None
    target_size: int | None
    quick_check: str | None
    notes_count: int | None
    tags_source: str | None
    backup_db: str | None
    status: str
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def discover_legacy_database_candidates(
    paths: AppPaths,
    *,
    worktree_root: str | Path,
    env: Mapping[str, str] | None = None,
) -> tuple[LegacyCandidate, ...]:
    root = Path(worktree_root).expanduser().resolve()
    values = os.environ if env is None else env
    raw_candidates: list[tuple[str, Path]] = []

    configured = values.get(LEGACY_DB_ENV, "").strip()
    if configured:
        raw_candidates.append(
            ("environment", _resolve_external_path(configured, base_directory=root))
        )

    raw_candidates.extend(
        [
            (
                "current_worktree_legacy_service",
                root / "pc-app-build" / "services" / "notes-api" / "data" / "notes.db",
            ),
            (
                "sibling_legacy_worktree",
                root.parent
                / "note-assistant-app"
                / "pc-app-build"
                / "services"
                / "notes-api"
                / "data"
                / "notes.db",
            ),
            (
                "transition_app_data",
                root / "pc-app-build" / "apps" / "notes-pyside" / "app" / "data" / "notes.db",
            ),
        ]
    )
    return _deduplicate_candidates(raw_candidates, target=paths.notes_db)


def discover_legacy_tag_candidates(
    paths: AppPaths,
    *,
    worktree_root: str | Path,
    env: Mapping[str, str] | None = None,
) -> tuple[LegacyCandidate, ...]:
    root = Path(worktree_root).expanduser().resolve()
    values = os.environ if env is None else env
    raw_candidates: list[tuple[str, Path]] = []

    configured = values.get(LEGACY_TAGS_ENV, "").strip()
    if configured:
        raw_candidates.append(
            ("environment", _resolve_external_path(configured, base_directory=root))
        )

    raw_candidates.extend(
        [
            (
                "current_worktree_app_data",
                root
                / "pc-app-build"
                / "apps"
                / "notes-pyside"
                / "app"
                / "data"
                / "custom_tags.json",
            ),
            (
                "sibling_legacy_worktree",
                root.parent
                / "note-assistant-app"
                / "pc-app-build"
                / "apps"
                / "notes-pyside"
                / "app"
                / "data"
                / "custom_tags.json",
            ),
        ]
    )
    return _deduplicate_candidates(raw_candidates, target=paths.custom_tags)


def inspect_database(database_path: str | Path) -> DatabaseInspection:
    path = Path(database_path).expanduser().resolve()
    if not path.is_file():
        raise DatabaseValidationError(
            path,
            "file does not exist or is not a regular file",
        )

    try:
        with closing(
            sqlite3.connect(
                _read_only_sqlite_uri(path),
                uri=True,
            )
        ) as connection:
            quick_rows = connection.execute("PRAGMA quick_check").fetchall()
            quick_check = "; ".join(str(row[0]) for row in quick_rows)
            if quick_rows != [("ok",)]:
                raise DatabaseValidationError(
                    path,
                    f"PRAGMA quick_check returned {quick_check}",
                )

            table_row = connection.execute(
                "SELECT name "
                "FROM sqlite_master "
                "WHERE type='table' AND name='notes'"
            ).fetchone()
            if table_row is None:
                raise DatabaseValidationError(
                    path,
                    "notes table is missing",
                )

            columns = frozenset(
                str(row[1])
                for row in connection.execute("PRAGMA table_info(notes)")
            )
            missing = tuple(sorted(REQUIRED_NOTE_COLUMNS - columns))
            if missing:
                raise LegacySchemaError(path, missing)

            notes_count = int(
                connection.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
            )
    except DataPreparationError:
        raise
    except (OSError, sqlite3.DatabaseError) as exc:
        raise DatabaseValidationError(path, str(exc)) from exc

    return DatabaseInspection(
        path=path,
        quick_check=quick_check,
        columns=columns,
        notes_count=notes_count,
    )


def read_tag_file(tag_path: str | Path) -> tuple[str, ...]:
    path = Path(tag_path).expanduser().resolve()
    if not path.is_file():
        raise TagFileValidationError(path, "file does not exist or is not a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TagFileValidationError(path, str(exc)) from exc
    if not isinstance(value, list):
        raise TagFileValidationError(path, "root JSON value must be an array")
    if any(not isinstance(item, str) for item in value):
        raise TagFileValidationError(path, "every tag must be a string")
    return _normalize_tags(value)


def prepare_gate1_local_data(
    paths: AppPaths,
    *,
    worktree_root: str | Path,
    env: Mapping[str, str] | None = None,
    now_provider: Callable[[], datetime] | None = None,
) -> MigrationResult:
    """Validate or create local data without ever deleting or overwriting legacy files."""

    clock = now_provider or _utc_now
    started = _as_utc(clock())
    paths.ensure_directories()
    report_path = paths.logs_dir / MIGRATION_REPORT_NAME

    source_db: Path | None = None
    backup_db: Path | None = None
    tags_source: Path | None = None
    inspection: DatabaseInspection | None = None
    status = "failed"

    try:
        had_successful_report = _has_successful_report(report_path)
        target_existed_at_start = paths.notes_db.exists()
        if target_existed_at_start:
            try:
                inspection = inspect_database(paths.notes_db)
            except DatabaseValidationError:
                backup_db = _backup_corrupt_database(paths.notes_db, paths.backups_dir, clock())
                raise
            status = "existing"
        else:
            candidates = discover_legacy_database_candidates(
                paths,
                worktree_root=worktree_root,
                env=env,
            )
            if len(candidates) > 1:
                raise MigrationConflictError(
                    "database", tuple(candidate.path for candidate in candidates)
                )
            if candidates:
                source_db = candidates[0].path
                inspect_database(source_db)
                _migrate_database(source_db, paths.notes_db)
                inspection = inspect_database(paths.notes_db)
                status = "migrated"
            else:
                _create_empty_database(paths.notes_db)
                inspection = inspect_database(paths.notes_db)
                status = "created_empty"

        tags_source = _prepare_tag_file(
            paths,
            worktree_root=worktree_root,
            env=env,
        )

        if not had_successful_report or not target_existed_at_start:
            backup_db = _create_verified_backup(
                paths.notes_db,
                paths.backups_dir,
                prefix="notes-pre-gate1",
                now=clock(),
            )

        finished = _as_utc(clock())
        report = _build_report(
            started=started,
            finished=finished,
            source_db=source_db,
            target_db=paths.notes_db,
            backup_db=backup_db,
            tags_source=tags_source,
            inspection=inspection,
            status=status,
            error=None,
        )
        _write_report(report_path, report)
        return MigrationResult(
            status=status,
            source_db=source_db,
            target_db=paths.notes_db,
            backup_db=backup_db,
            tags_source=tags_source,
            notes_count=inspection.notes_count,
            report_path=report_path,
        )
    except Exception as exc:
        finished = _as_utc(clock())
        report = _build_report(
            started=started,
            finished=finished,
            source_db=source_db,
            target_db=paths.notes_db,
            backup_db=backup_db,
            tags_source=tags_source,
            inspection=inspection,
            status="failed",
            error=str(exc),
        )
        try:
            _write_report(report_path, report)
        except OSError:
            pass
        raise


def _prepare_tag_file(
    paths: AppPaths,
    *,
    worktree_root: str | Path,
    env: Mapping[str, str] | None,
) -> Path | None:
    if paths.custom_tags.exists():
        read_tag_file(paths.custom_tags)
        return None

    candidates = discover_legacy_tag_candidates(
        paths,
        worktree_root=worktree_root,
        env=env,
    )
    if len(candidates) > 1:
        raise MigrationConflictError("tag file", tuple(candidate.path for candidate in candidates))
    if not candidates:
        return None

    source = candidates[0].path
    tags = read_tag_file(source)
    _write_json_atomic(paths.custom_tags, list(tags))
    return source


def _create_empty_database(target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    engine = create_sqlite_engine(target)
    try:
        initialize_database(engine)
    finally:
        engine.dispose()


def _migrate_database(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.gate1.tmp")
    temporary.unlink(missing_ok=True)

    try:
        _sqlite_backup(source, temporary)
        inspect_database(temporary)
        os.replace(temporary, target)
    except Exception:
        # 清理失败不能掩盖最初的迁移异常。
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _create_verified_backup(
    source: Path,
    backup_directory: Path,
    *,
    prefix: str,
    now: datetime,
) -> Path:
    backup_directory.mkdir(parents=True, exist_ok=True)
    destination = _unique_timestamp_path(backup_directory, prefix, ".db", now)
    _sqlite_backup(source, destination)
    inspect_database(destination)
    return destination


def _backup_corrupt_database(source: Path, backup_directory: Path, now: datetime) -> Path:
    backup_directory.mkdir(parents=True, exist_ok=True)
    destination = _unique_timestamp_path(backup_directory, "notes-corrupt", ".db", now)
    shutil.copy2(source, destination)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{source}{suffix}")
        if sidecar.is_file():
            shutil.copy2(sidecar, Path(f"{destination}{suffix}"))
    return destination


def _sqlite_backup(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)

    try:
        with (
            closing(
                sqlite3.connect(
                    _read_only_sqlite_uri(source),
                    uri=True,
                )
            ) as source_connection,
            closing(sqlite3.connect(destination)) as destination_connection,
        ):
            source_connection.backup(destination_connection)
            destination_connection.commit()
    except (OSError, sqlite3.DatabaseError) as exc:
        destination.unlink(missing_ok=True)
        raise DatabaseValidationError(
            source,
            f"SQLite backup failed: {exc}",
        ) from exc


def _build_report(
    *,
    started: datetime,
    finished: datetime,
    source_db: Path | None,
    target_db: Path,
    backup_db: Path | None,
    tags_source: Path | None,
    inspection: DatabaseInspection | None,
    status: str,
    error: str | None,
) -> MigrationReport:
    return MigrationReport(
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        source_db=str(source_db) if source_db is not None else None,
        target_db=str(target_db),
        source_size=_safe_file_size(source_db),
        target_size=_safe_file_size(target_db),
        quick_check=inspection.quick_check if inspection is not None else None,
        notes_count=inspection.notes_count if inspection is not None else None,
        tags_source=str(tags_source) if tags_source is not None else None,
        backup_db=str(backup_db) if backup_db is not None else None,
        status=status,
        error=error,
    )


def _write_report(path: Path, report: MigrationReport) -> None:
    _write_json_atomic(path, report.to_dict())


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _deduplicate_candidates(
    raw_candidates: Sequence[tuple[str, Path]],
    *,
    target: Path,
) -> tuple[LegacyCandidate, ...]:
    result: list[LegacyCandidate] = []
    target_resolved = target.expanduser().resolve()
    for label, raw_path in raw_candidates:
        path = raw_path.expanduser().resolve()
        if not path.is_file() or _paths_refer_to_same_file(path, target_resolved):
            continue
        if any(_paths_refer_to_same_file(path, item.path) for item in result):
            continue
        result.append(LegacyCandidate(label=label, path=path))
    return tuple(result)


def _paths_refer_to_same_file(left: Path, right: Path) -> bool:
    if left.resolve() == right.resolve():
        return True
    if left.exists() and right.exists():
        try:
            return os.path.samefile(left, right)
        except OSError:
            return False
    return False


def _resolve_external_path(value: str, *, base_directory: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_directory / path
    return path.resolve()


def _read_only_sqlite_uri(path: Path) -> str:
    return f"{path.resolve().as_uri()}?mode=ro"


def _normalize_tags(values: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        tag = item.strip()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        result.append(tag)
    return tuple(result)


def _unique_timestamp_path(
    directory: Path,
    prefix: str,
    suffix: str,
    now: datetime,
) -> Path:
    timestamp = _as_utc(now).strftime("%Y%m%d-%H%M%S")
    candidate = directory / f"{prefix}-{timestamp}{suffix}"
    index = 1
    while candidate.exists():
        candidate = directory / f"{prefix}-{timestamp}-{index}{suffix}"
        index += 1
    return candidate


def _has_successful_report(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return isinstance(value, dict) and value.get("status") in _SUCCESS_STATUSES


def _safe_file_size(path: Path | None) -> int | None:
    if path is None:
        return None
    try:
        return path.stat().st_size
    except OSError:
        return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
