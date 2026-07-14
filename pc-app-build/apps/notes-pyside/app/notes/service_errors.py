"""Application-level note errors and repository call translation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from .database_executor import DatabaseExecutor, DatabaseExecutorClosedError
from .repository import NoteNotFoundError, NoteRepositoryError, NoteStateError

T = TypeVar("T")


class NoteServiceError(RuntimeError):
    """Base error exposed by note application services."""

    code = "note_service_error"

    def __init__(self, operation: str, message: str) -> None:
        self.operation = operation
        super().__init__(message)


class NoteServiceNotFoundError(NoteServiceError):
    code = "note_not_found"

    def __init__(self, operation: str, missing_ids: tuple[int, ...]) -> None:
        self.missing_ids = missing_ids
        super().__init__(operation, f"notes not found: {missing_ids}")


class NoteServiceStateError(NoteServiceError):
    code = "invalid_note_state"

    def __init__(
        self,
        operation: str,
        invalid_ids: tuple[int, ...],
        expected_state: str,
    ) -> None:
        self.invalid_ids = invalid_ids
        self.expected_state = expected_state
        super().__init__(
            operation,
            f"notes {invalid_ids} are not in expected state: {expected_state}",
        )


class NoteServiceUnavailableError(NoteServiceError):
    code = "note_service_unavailable"

    def __init__(self, operation: str) -> None:
        super().__init__(operation, "note database service is closing or closed")


class NoteServiceRepositoryError(NoteServiceError):
    code = "note_repository_error"

    def __init__(self, operation: str, cause: NoteRepositoryError) -> None:
        self.cause = cause
        super().__init__(operation, str(cause))


async def run_repository_call(
    executor: DatabaseExecutor,
    operation: str,
    call: Callable[..., T],
    /,
    *args: Any,
    **kwargs: Any,
) -> T:
    """Run one repository call and translate known infrastructure errors."""

    try:
        return await executor.run(call, *args, **kwargs)
    except DatabaseExecutorClosedError as exc:
        raise NoteServiceUnavailableError(operation) from exc
    except NoteNotFoundError as exc:
        raise NoteServiceNotFoundError(operation, exc.missing_ids) from exc
    except NoteStateError as exc:
        raise NoteServiceStateError(
            operation,
            exc.invalid_ids,
            exc.expected_state,
        ) from exc
    except NoteRepositoryError as exc:
        raise NoteServiceRepositoryError(operation, exc) from exc
