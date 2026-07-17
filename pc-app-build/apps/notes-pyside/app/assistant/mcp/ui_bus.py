"""Qt-independent, generation-safe UI command bus for Gate 5.1."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from .contracts import JsonValue


class UiCommandKind(str, Enum):
    OPEN_NOTE = "open_note"
    SHOW_SEARCH = "show_search"
    SHOW_NOTE_LIST = "show_note_list"
    SHOW_TAG = "show_tag"
    SHOW_TRASH = "show_trash"
    SHOW_PINNED = "show_pinned"
    SHOW_CONFIRMATION = "show_confirmation"
    REFRESH_CURRENT = "refresh_current"
    REFRESH_TAGS = "refresh_tags"


@dataclass(frozen=True, slots=True)
class UiCommand:
    kind: UiCommandKind
    payload: Mapping[str, JsonValue] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class UiDispatchResult:
    accepted: bool
    message: str
    error_code: str | None = None


class UiCommandAdapter(Protocol):
    async def dispatch(self, command: UiCommand) -> UiDispatchResult: ...


class UiCommandBus:
    """Own one replaceable UI adapter without detached dispatch tasks."""

    def __init__(self) -> None:
        self._adapter: UiCommandAdapter | None = None
        self._generation = 0
        self._closed = False
        self._active_dispatches = 0
        self._lock = asyncio.Lock()

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def adapter_available(self) -> bool:
        return not self._closed and self._adapter is not None

    @property
    def active_dispatch_count(self) -> int:
        return self._active_dispatches

    def bind(self, adapter: UiCommandAdapter) -> int:
        if self._closed:
            raise RuntimeError("UI command bus is closed")
        self._generation += 1
        self._adapter = adapter
        return self._generation

    def unbind(self, generation: int) -> bool:
        if generation != self._generation:
            return False
        self._generation += 1
        self._adapter = None
        return True

    async def dispatch(self, command: UiCommand) -> UiDispatchResult:
        async with self._lock:
            if self._closed or self._adapter is None:
                return UiDispatchResult(False, "桌面 UI 当前不可用", "ui_unavailable")
            adapter = self._adapter
            generation = self._generation
            self._active_dispatches += 1
        try:
            result = await adapter.dispatch(command)
        except asyncio.CancelledError:
            raise
        except Exception:
            return UiDispatchResult(False, "UI 命令执行失败", "ui_dispatch_failed")
        finally:
            async with self._lock:
                self._active_dispatches -= 1
        if generation != self._generation or adapter is not self._adapter:
            return UiDispatchResult(
                False, "UI generation 已变化，命令结果被丢弃", "stale_ui_generation"
            )
        return result

    async def close(self) -> None:
        async with self._lock:
            self._closed = True
            self._generation += 1
            adapter = self._adapter
            self._adapter = None
        close = getattr(adapter, "close", None)
        if close is not None:
            result = close()
            if asyncio.iscoroutine(result):
                await result


__all__ = [
    "UiCommand",
    "UiCommandAdapter",
    "UiCommandBus",
    "UiCommandKind",
    "UiDispatchResult",
]
