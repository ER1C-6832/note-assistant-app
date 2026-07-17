"""Gate 5.1 read/resolve and UI tool executor."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime

from ...notes import Note, NoteQueryService, NoteServiceError
from .constants import MCP_MAX_RESULT_BYTES
from .contracts import JsonValue, ToolCall, ToolDescriptor, ToolExecutor, ToolResult
from .intent_rules import (
    extract_explicit_note_id,
    extract_search_terms,
    is_contextual_reference,
)
from .registry import GateNotReadyExecutor
from .ui_bus import UiCommand, UiCommandBus, UiCommandKind

READ_TOOL_NAMES = frozenset(
    {
        "notes.resolve",
        "notes.search",
        "notes.list_recent",
        "notes.get",
        "notes.list_by_tag",
        "notes.list_deleted",
        "notes.list_todos",
        "notes.list_pinned",
    }
)
UI_TOOL_NAMES = frozenset(
    {
        "ui.open_note",
        "ui.show_search",
        "ui.show_note_list",
        "ui.show_tag",
        "ui.show_trash",
        "ui.show_pinned",
        "ui.show_confirmation",
    }
)

_TODO_TAG = "待办"
_LIST_DEFAULTS = {
    "notes.list_recent": 5,
    "notes.list_by_tag": 20,
    "notes.list_deleted": 20,
    "notes.list_todos": 20,
    "notes.list_pinned": 20,
}


@dataclass(frozen=True, slots=True)
class _Resolution:
    status: str
    candidates: tuple[Note, ...]


class Gate51ToolExecutor:
    """Execute only Gate 5.1 tools and fail closed for later Gate handlers."""

    def __init__(
        self,
        query_service: NoteQueryService,
        ui_bus: UiCommandBus,
        *,
        fallback: ToolExecutor | None = None,
    ) -> None:
        self._queries = query_service
        self._ui_bus = ui_bus
        self._fallback = fallback or GateNotReadyExecutor()

    async def execute(self, call: ToolCall, descriptor: ToolDescriptor) -> ToolResult:
        try:
            if call.tool_name in READ_TOOL_NAMES:
                return await self._execute_read(call, descriptor)
            if call.tool_name in UI_TOOL_NAMES:
                return await self._execute_ui(call, descriptor)
            return await self._fallback.execute(call, descriptor)
        except NoteServiceError as exc:
            return ToolResult(
                status="failed",
                message="便签查询服务暂时不可用",
                tool_name=call.tool_name,
                risk=descriptor.risk,
                error_code=exc.code,
            )
        except (TypeError, ValueError):
            return ToolResult(
                status="failed",
                message="工具参数无法安全处理",
                tool_name=call.tool_name,
                risk=descriptor.risk,
                error_code="invalid_tool_arguments",
            )
        except Exception:
            return ToolResult(
                status="failed",
                message="工具执行失败",
                tool_name=call.tool_name,
                risk=descriptor.risk,
                error_code="tool_execution_failed",
            )

    async def _execute_read(self, call: ToolCall, descriptor: ToolDescriptor) -> ToolResult:
        args = call.arguments
        name = call.tool_name
        if name == "notes.get":
            note = await self._queries.get(
                int(args["note_id"]), bool(args.get("include_deleted", False))
            )
            if note is None:
                return self._not_found(name, descriptor)
            return self._success(
                name,
                descriptor,
                "已读取便签",
                {"note": _full_note(note)},
                affected_note_ids=(note.id,),
            )
        if name == "notes.search":
            raw_query = str(args["query"])
            terms = extract_search_terms(raw_query) or (raw_query.strip(),)
            tags = _strings(args.get("tags", ()))
            scope = str(args.get("scope", "active"))
            limit = int(args.get("limit", 10))
            search_terms = getattr(self._queries, "search_terms_filtered", None)
            if search_terms is None:
                notes = await self._queries.search_filtered(
                    terms[0], tags=tags, scope=scope, limit=limit
                )
            else:
                notes = await search_terms(terms, tags=tags, scope=scope, limit=limit)
            return self._list_result(name, descriptor, notes, "搜索完成")
        if name == "notes.list_recent":
            notes = await self._queries.list_recent(int(args.get("limit", 5)))
            return self._list_result(name, descriptor, notes, "最近便签已列出")
        if name == "notes.list_by_tag":
            notes = await self._queries.list_by_tag_bounded(
                str(args["tag"]), int(args.get("limit", 20))
            )
            return self._list_result(name, descriptor, notes, "标签便签已列出")
        if name == "notes.list_deleted":
            notes = await self._queries.list_deleted_bounded(int(args.get("limit", 20)))
            return self._list_result(name, descriptor, notes, "已删除便签已列出")
        if name == "notes.list_todos":
            notes = await self._queries.list_by_tag_bounded(_TODO_TAG, int(args.get("limit", 20)))
            return self._list_result(name, descriptor, notes, "待办便签已列出")
        if name == "notes.list_pinned":
            notes = await self._queries.list_pinned_bounded(int(args.get("limit", 20)))
            return self._list_result(name, descriptor, notes, "置顶便签已列出")
        if name == "notes.resolve":
            resolution = await self._resolve(args)
            candidates = tuple(_summary(note) for note in resolution.candidates)
            if resolution.status == "not_found":
                return self._not_found(name, descriptor)
            if resolution.status == "ambiguous":
                return self._success(
                    name,
                    descriptor,
                    "存在多个候选，未自动选择",
                    {
                        "resolution_status": "ambiguous",
                        "note_id": None,
                        "candidates": list(candidates),
                    },
                )
            note = resolution.candidates[0]
            return self._success(
                name,
                descriptor,
                "已解析唯一便签",
                {
                    "resolution_status": "resolved",
                    "note_id": note.id,
                    "candidates": list(candidates),
                },
                affected_note_ids=(note.id,),
            )
        raise ValueError(f"unsupported Gate 5.1 read tool: {name}")

    async def _execute_ui(self, call: ToolCall, descriptor: ToolDescriptor) -> ToolResult:
        name = call.tool_name
        args = call.arguments
        if name == "ui.show_confirmation":
            return ToolResult(
                status="blocked",
                message="Gate 5.1 尚无可展示的 pending confirmation",
                tool_name=name,
                risk=descriptor.risk,
                error_code="confirmation_not_ready",
            )
        if name == "ui.open_note":
            note_id = int(args["note_id"])
            active = await self._queries.get(note_id)
            if active is None:
                existing = await self._queries.get(note_id, include_deleted=True)
                if existing is not None and existing.is_deleted:
                    return ToolResult(
                        status="blocked",
                        message="已删除便签不能在活动视图中打开",
                        tool_name=name,
                        risk=descriptor.risk,
                        error_code="note_deleted",
                    )
                return self._not_found(name, descriptor)
            command = UiCommand(UiCommandKind.OPEN_NOTE, {"note_id": note_id})
        elif name == "ui.show_search":
            command = UiCommand(UiCommandKind.SHOW_SEARCH, {"query": str(args.get("query", ""))})
        elif name == "ui.show_note_list":
            command = UiCommand(UiCommandKind.SHOW_NOTE_LIST)
        elif name == "ui.show_tag":
            command = UiCommand(UiCommandKind.SHOW_TAG, {"tag": str(args["tag"])})
        elif name == "ui.show_trash":
            command = UiCommand(UiCommandKind.SHOW_TRASH)
        elif name == "ui.show_pinned":
            command = UiCommand(UiCommandKind.SHOW_PINNED)
        else:
            raise ValueError(f"unsupported Gate 5.1 UI tool: {name}")

        dispatched = await self._ui_bus.dispatch(command)
        if not dispatched.accepted:
            return ToolResult(
                status="blocked",
                message=dispatched.message,
                tool_name=name,
                risk=descriptor.risk,
                error_code=dispatched.error_code or "ui_dispatch_blocked",
            )
        return self._success(name, descriptor, dispatched.message, {"dispatched": True})

    async def _resolve(self, args: Mapping[str, JsonValue]) -> _Resolution:
        scope = str(args.get("scope", "active"))
        limit = int(args.get("limit", 5))
        exact_title = str(args.get("exact_title", "")).strip()
        query = str(args.get("query", "")).strip()

        explicit_id = extract_explicit_note_id(query)
        if explicit_id is None and query.isdecimal() and int(query) > 0:
            explicit_id = int(query)
        if explicit_id is not None:
            note = await self._queries.get(explicit_id, include_deleted=scope != "active")
            if note is not None and _scope_matches(note, scope):
                return _Resolution("resolved", (note,))
            return _Resolution("not_found", ())

        pool = await self._queries.list_scope_bounded(scope, max(100, limit * 20))
        if exact_title:
            exact = tuple(
                note for note in pool if _normalized(note.title) == _normalized(exact_title)
            )
            return _resolution_from_candidates(exact[:limit])

        if is_contextual_reference(query):
            # A bare ‘刚才那条/那个’ has no stable conversation-local target in
            # the client.  Resolve only when the selected scope itself has one
            # candidate; otherwise return recent candidates for clarification.
            return _resolution_from_candidates(tuple(pool[:limit]))

        terms = extract_search_terms(query) or ((_normalized(query),) if query else ())
        if not terms:
            return _Resolution("not_found", ())

        primary = _normalized(terms[0])
        exact = tuple(note for note in pool if _normalized(note.title) == primary)
        if exact:
            return _resolution_from_candidates(exact[:limit])

        precise = tuple(note for note in pool if _matches_query(note, primary))
        if precise:
            ranked = sorted(
                precise,
                key=lambda note: (
                    _rank_terms(note, (primary,)),
                    note.updated_at,
                    note.id,
                ),
                reverse=True,
            )
            return _resolution_from_candidates(tuple(ranked[:limit]))

        normalized_terms = tuple(_normalized(term) for term in terms if _normalized(term))
        ranked = sorted(
            (note for note in pool if any(_matches_query(note, term) for term in normalized_terms)),
            key=lambda note: (
                _rank_terms(note, normalized_terms),
                note.updated_at,
                note.id,
            ),
            reverse=True,
        )
        return _resolution_from_candidates(tuple(ranked[:limit]))

    def _list_result(
        self,
        name: str,
        descriptor: ToolDescriptor,
        notes: tuple[Note, ...],
        message: str,
    ) -> ToolResult:
        return self._success(
            name,
            descriptor,
            message,
            {"count": len(notes), "notes": [_summary(note) for note in notes]},
            affected_note_ids=tuple(note.id for note in notes),
        )

    @staticmethod
    def _not_found(name: str, descriptor: ToolDescriptor) -> ToolResult:
        return ToolResult(
            status="failed",
            message="未找到符合条件的便签",
            tool_name=name,
            risk=descriptor.risk,
            error_code="note_not_found",
        )

    @staticmethod
    def _success(
        name: str,
        descriptor: ToolDescriptor,
        message: str,
        result: Mapping[str, JsonValue],
        *,
        affected_note_ids: tuple[int, ...] = (),
    ) -> ToolResult:
        bounded = _bound_result(dict(result))
        return ToolResult(
            status="success",
            message=message,
            tool_name=name,
            risk=descriptor.risk,
            affected_note_ids=affected_note_ids,
            result=bounded,
        )


def _resolution_from_candidates(candidates: tuple[Note, ...]) -> _Resolution:
    if not candidates:
        return _Resolution("not_found", ())
    if len(candidates) == 1:
        return _Resolution("resolved", candidates)
    return _Resolution("ambiguous", candidates)


def _scope_matches(note: Note, scope: str) -> bool:
    if scope == "active":
        return not note.is_deleted
    if scope == "deleted":
        return note.is_deleted
    return True


def _matches_query(note: Note, normalized_query: str) -> bool:
    if not normalized_query:
        return False
    haystacks = (note.title, note.content, *note.tags)
    return any(normalized_query in _normalized(value) for value in haystacks)


def _rank(note: Note, normalized_query: str) -> int:
    title = _normalized(note.title)
    if title.startswith(normalized_query):
        return 4
    if normalized_query in title:
        return 3
    if any(normalized_query == _normalized(tag) for tag in note.tags):
        return 2
    return 1


def _rank_terms(note: Note, terms: tuple[str, ...]) -> tuple[int, int, int]:
    matched = tuple(term for term in terms if _matches_query(note, term))
    best = max((_rank(note, term) for term in matched), default=0)
    longest = max((len(term) for term in matched), default=0)
    return len(matched), best, longest


def _normalized(value: str) -> str:
    return " ".join(str(value).casefold().split())


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, bytearray)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _summary(note: Note) -> dict[str, JsonValue]:
    return {
        "note_id": note.id,
        "title": _truncate_utf8(note.title, 600),
        "snippet": _truncate_utf8(" ".join(note.content.split()), 900),
        "tags": list(note.tags[:20]),
        "pinned": note.is_pinned,
        "deleted": note.is_deleted,
        "updated_at": _iso(note.updated_at),
    }


def _full_note(note: Note) -> dict[str, JsonValue]:
    content, truncated = _truncate_utf8_with_flag(note.content, 20 * 1024)
    return {
        "note_id": note.id,
        "title": _truncate_utf8(note.title, 800),
        "content": content,
        "content_truncated": truncated,
        "tags": list(note.tags[:20]),
        "pinned": note.is_pinned,
        "deleted": note.is_deleted,
        "created_at": _iso(note.created_at),
        "updated_at": _iso(note.updated_at),
        "source": note.source.value,
    }


def _bound_result(payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    if len(encoded.encode("utf-8")) <= MCP_MAX_RESULT_BYTES - 2048:
        return payload
    notes = payload.get("notes")
    if isinstance(notes, list):
        while (
            notes
            and len(
                json.dumps(
                    payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
                ).encode("utf-8")
            )
            > MCP_MAX_RESULT_BYTES - 2048
        ):
            notes.pop()
        payload["count"] = len(notes)
        payload["truncated"] = True
    return payload


def _truncate_utf8(value: str, max_bytes: int) -> str:
    return _truncate_utf8_with_flag(value, max_bytes)[0]


def _truncate_utf8_with_flag(value: str, max_bytes: int) -> tuple[str, bool]:
    raw = str(value).encode("utf-8")
    if len(raw) <= max_bytes:
        return str(value), False
    shortened = raw[:max_bytes]
    while shortened:
        try:
            return shortened.decode("utf-8") + "…", True
        except UnicodeDecodeError:
            shortened = shortened[:-1]
    return "…", True


__all__ = ["Gate51ToolExecutor", "READ_TOOL_NAMES", "UI_TOOL_NAMES"]
