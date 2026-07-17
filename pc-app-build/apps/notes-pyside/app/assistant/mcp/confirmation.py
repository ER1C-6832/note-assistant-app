"""Bounded, single-use pending confirmation service for Gate 5.3."""

from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Protocol

from .contracts import JsonValue, ToolResult, ToolRisk

PENDING_CONFIRMATION_CAPACITY = 32
PENDING_CONFIRMATION_TTL_SECONDS = 120.0
_TERMINAL_HISTORY_CAPACITY = 128


class ConfirmationClock(Protocol):
    def monotonic(self) -> float: ...

    def now_utc(self) -> datetime: ...


class SystemConfirmationClock:
    def monotonic(self) -> float:
        return time.monotonic()

    def now_utc(self) -> datetime:
        return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class PendingConfirmation:
    confirmation_id: str
    connection_generation: int
    session_id: str = field(repr=False)
    tool_name: str
    risk: ToolRisk
    argument_fingerprint: str
    arguments_json: str = field(repr=False)
    preview: Mapping[str, JsonValue] = field(repr=False)
    affected_note_ids: tuple[int, ...]
    affected_tags: tuple[str, ...]
    target_versions: Mapping[int, str] = field(repr=False)
    created_at: datetime
    expires_at: datetime
    expires_monotonic: float = field(repr=False)

    def arguments(self) -> dict[str, JsonValue]:
        value = json.loads(self.arguments_json)
        if not isinstance(value, dict):
            raise ValueError("pending confirmation arguments are not an object")
        return value

    def public_dict(self, *, now_monotonic: float) -> dict[str, JsonValue]:
        remaining = max(0, int(self.expires_monotonic - now_monotonic))
        return {
            "confirmation_id": self.confirmation_id,
            "tool_name": self.tool_name,
            "risk": self.risk.value,
            "preview": dict(self.preview),
            "affected_note_ids": list(self.affected_note_ids),
            "affected_tags": list(self.affected_tags),
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "seconds_remaining": remaining,
        }


@dataclass(frozen=True, slots=True)
class ConfirmationResolution:
    status: str
    message: str
    error_code: str | None = None
    pending: PendingConfirmation | None = field(default=None, repr=False)
    tool_result: ToolResult | None = field(default=None, repr=False)
    terminal_state: str | None = None


@dataclass(frozen=True, slots=True)
class _TerminalConfirmation:
    state: str
    tool_name: str
    connection_generation: int
    session_id: str = field(repr=False)


ConfirmationExecutor = Callable[[PendingConfirmation], Awaitable[ToolResult]]


class PendingConfirmationService:
    """Own pending confirmation state and serialize every finalization race."""

    def __init__(
        self,
        *,
        capacity: int = PENDING_CONFIRMATION_CAPACITY,
        ttl_seconds: float = PENDING_CONFIRMATION_TTL_SECONDS,
        clock: ConfirmationClock | None = None,
    ) -> None:
        if capacity <= 0:
            raise ValueError("confirmation capacity must be positive")
        if ttl_seconds <= 0:
            raise ValueError("confirmation TTL must be positive")
        self._capacity = capacity
        self._ttl_seconds = ttl_seconds
        self._clock = clock or SystemConfirmationClock()
        self._pending: OrderedDict[str, PendingConfirmation] = OrderedDict()
        self._terminal: OrderedDict[str, _TerminalConfirmation] = OrderedDict()
        self._lock = asyncio.Lock()
        self._closed = False

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def terminal_count(self) -> int:
        return len(self._terminal)

    @property
    def closed(self) -> bool:
        return self._closed

    def public_view(self, pending: PendingConfirmation) -> dict[str, JsonValue]:
        return pending.public_dict(now_monotonic=self._clock.monotonic())

    async def create(
        self,
        *,
        connection_generation: int,
        session_id: str,
        tool_name: str,
        risk: ToolRisk,
        arguments: Mapping[str, JsonValue],
        preview: Mapping[str, JsonValue],
        affected_note_ids: tuple[int, ...] = (),
        affected_tags: tuple[str, ...] = (),
        target_versions: Mapping[int, str] | None = None,
    ) -> PendingConfirmation | None:
        clean_session = session_id.strip()
        if connection_generation <= 0 or not clean_session:
            return None
        arguments_json = _canonical_json(arguments)
        fingerprint = hashlib.sha256(f"{tool_name}\n{arguments_json}".encode("utf-8")).hexdigest()
        now_monotonic = self._clock.monotonic()
        now_utc = self._clock.now_utc()
        async with self._lock:
            if self._closed:
                return None
            self._expire_locked(now_monotonic)
            if len(self._pending) >= self._capacity:
                return None
            confirmation_id = self._new_id_locked()
            pending = PendingConfirmation(
                confirmation_id=confirmation_id,
                connection_generation=connection_generation,
                session_id=clean_session,
                tool_name=tool_name,
                risk=risk,
                argument_fingerprint=fingerprint,
                arguments_json=arguments_json,
                preview=dict(preview),
                affected_note_ids=tuple(affected_note_ids),
                affected_tags=tuple(affected_tags),
                target_versions=dict(target_versions or {}),
                created_at=now_utc,
                expires_at=now_utc + timedelta(seconds=self._ttl_seconds),
                expires_monotonic=now_monotonic + self._ttl_seconds,
            )
            self._pending[confirmation_id] = pending
            return pending

    async def get(
        self,
        confirmation_id: str,
        *,
        connection_generation: int,
        session_id: str | None,
        trusted_local: bool = False,
    ) -> ConfirmationResolution:
        async with self._lock:
            self._expire_locked(self._clock.monotonic())
            return self._lookup_locked(
                confirmation_id,
                connection_generation=connection_generation,
                session_id=session_id,
                trusted_local=trusted_local,
            )

    async def list_for_context(
        self,
        *,
        connection_generation: int,
        session_id: str | None,
        trusted_local: bool = False,
    ) -> tuple[dict[str, JsonValue], ...]:
        now = self._clock.monotonic()
        async with self._lock:
            self._expire_locked(now)
            values = tuple(self._pending.values())
            if not trusted_local:
                clean_session = (session_id or "").strip()
                values = tuple(
                    pending
                    for pending in values
                    if pending.connection_generation == connection_generation
                    and pending.session_id == clean_session
                )
            return tuple(pending.public_dict(now_monotonic=now) for pending in values)

    async def reject(
        self,
        confirmation_id: str,
        *,
        connection_generation: int,
        session_id: str | None,
        trusted_local: bool = False,
    ) -> ConfirmationResolution:
        async with self._lock:
            self._expire_locked(self._clock.monotonic())
            lookup = self._lookup_locked(
                confirmation_id,
                connection_generation=connection_generation,
                session_id=session_id,
                trusted_local=trusted_local,
            )
            if lookup.status != "pending" or lookup.pending is None:
                return lookup
            pending = self._pending.pop(confirmation_id)
            self._remember_terminal_locked(pending, "rejected")
            return ConfirmationResolution(
                status="rejected",
                message="已拒绝该操作",
                pending=pending,
                terminal_state="rejected",
            )

    async def confirm(
        self,
        confirmation_id: str,
        *,
        connection_generation: int,
        session_id: str | None,
        executor: ConfirmationExecutor,
        trusted_local: bool = False,
    ) -> ConfirmationResolution:
        async with self._lock:
            self._expire_locked(self._clock.monotonic())
            lookup = self._lookup_locked(
                confirmation_id,
                connection_generation=connection_generation,
                session_id=session_id,
                trusted_local=trusted_local,
            )
            if lookup.status != "pending" or lookup.pending is None:
                return lookup
            pending = self._pending.pop(confirmation_id)
            self._remember_terminal_locked(pending, "executing")

        try:
            result = await executor(pending)
        except asyncio.CancelledError:
            async with self._lock:
                self._remember_terminal_locked(pending, "cancelled")
            raise
        except Exception:
            async with self._lock:
                self._remember_terminal_locked(pending, "failed")
            return ConfirmationResolution(
                status="execution_failed",
                message="确认后的操作执行失败",
                error_code="confirmation_execution_failed",
                pending=pending,
                terminal_state="failed",
            )

        terminal_state = (
            "confirmed" if result.status in {"success", "partial_success"} else "failed"
        )
        async with self._lock:
            self._remember_terminal_locked(pending, terminal_state)
        return ConfirmationResolution(
            status="confirmed" if terminal_state == "confirmed" else "execution_failed",
            message=result.message,
            error_code=result.error_code,
            pending=pending,
            tool_result=result,
            terminal_state=terminal_state,
        )

    async def invalidate_generation(self, generation: int, reason: str) -> int:
        state = "disconnected" if reason else "invalidated"
        async with self._lock:
            matches = [
                pending
                for pending in self._pending.values()
                if pending.connection_generation == generation
            ]
            for pending in matches:
                self._pending.pop(pending.confirmation_id, None)
                self._remember_terminal_locked(pending, state)
            return len(matches)

    async def invalidate_all(self, reason: str = "shutdown") -> int:
        state = "closed" if reason == "shutdown" else "invalidated"
        async with self._lock:
            matches = tuple(self._pending.values())
            self._pending.clear()
            for pending in matches:
                self._remember_terminal_locked(pending, state)
            return len(matches)

    async def close(self) -> None:
        async with self._lock:
            if self._closed:
                return
            self._closed = True
            matches = tuple(self._pending.values())
            self._pending.clear()
            for pending in matches:
                self._remember_terminal_locked(pending, "closed")

    def _lookup_locked(
        self,
        confirmation_id: str,
        *,
        connection_generation: int,
        session_id: str | None,
        trusted_local: bool,
    ) -> ConfirmationResolution:
        clean_id = str(confirmation_id).strip()
        if not clean_id:
            return ConfirmationResolution("not_found", "确认请求不存在", "confirmation_not_found")
        pending = self._pending.get(clean_id)
        if pending is None:
            terminal = self._terminal.get(clean_id)
            if terminal is None:
                return ConfirmationResolution(
                    "not_found", "确认请求不存在", "confirmation_not_found"
                )
            code = (
                "confirmation_expired" if terminal.state == "expired" else "confirmation_consumed"
            )
            return ConfirmationResolution(
                "consumed",
                "确认请求已失效或已被处理",
                code,
                terminal_state=terminal.state,
            )
        if not trusted_local:
            clean_session = (session_id or "").strip()
            if (
                pending.connection_generation != connection_generation
                or pending.session_id != clean_session
            ):
                return ConfirmationResolution(
                    "wrong_context",
                    "确认请求不属于当前会话",
                    "confirmation_context_mismatch",
                )
        return ConfirmationResolution("pending", "等待确认", pending=pending)

    def _expire_locked(self, now_monotonic: float) -> None:
        expired = [
            pending
            for pending in self._pending.values()
            if pending.expires_monotonic <= now_monotonic
        ]
        for pending in expired:
            self._pending.pop(pending.confirmation_id, None)
            self._remember_terminal_locked(pending, "expired")

    def _remember_terminal_locked(self, pending: PendingConfirmation, state: str) -> None:
        self._terminal[pending.confirmation_id] = _TerminalConfirmation(
            state=state,
            tool_name=pending.tool_name,
            connection_generation=pending.connection_generation,
            session_id=pending.session_id,
        )
        self._terminal.move_to_end(pending.confirmation_id)
        while len(self._terminal) > _TERMINAL_HISTORY_CAPACITY:
            self._terminal.popitem(last=False)

    def _new_id_locked(self) -> str:
        while True:
            value = secrets.token_urlsafe(18)
            if value not in self._pending and value not in self._terminal:
                return value


def _canonical_json(value: Mapping[str, JsonValue]) -> str:
    return json.dumps(
        dict(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


__all__ = [
    "ConfirmationResolution",
    "PENDING_CONFIRMATION_CAPACITY",
    "PENDING_CONFIRMATION_TTL_SECONDS",
    "PendingConfirmation",
    "PendingConfirmationService",
    "SystemConfirmationClock",
]
