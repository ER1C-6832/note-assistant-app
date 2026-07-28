"""Bounded single-worker MCP coordinator with generation-scoped ownership."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import OrderedDict, deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TypeAlias

from .constants import (
    JSONRPC_INVALID_REQUEST,
    JSONRPC_SERVER_BUSY,
    MCP_DEDUPE_CAPACITY,
    MCP_MAX_DUPLICATE_WAITERS,
    MCP_MAX_RESULT_BYTES,
    MCP_PROTOCOL_VERSION,
    MCP_REQUEST_QUEUE_CAPACITY,
    MCP_SERVER_NAME,
    MCP_SERVER_VERSION,
    MCP_WORKER_CLOSE_TIMEOUT_SECONDS,
)
from .contracts import (
    JsonValue,
    McpLifecycleSink,
    McpLifecycleSummary,
    McpNotification,
    McpParseFailure,
    McpRequest,
    McpResponseSink,
    RequestId,
    ToolCall,
    ToolResult,
    ToolRisk,
)
from .jsonrpc import (
    error_response,
    internal_error,
    invalid_params,
    method_not_found,
    parse_jsonrpc_payload,
    success_response,
)
from .registry import SchemaValidationError, ToolRegistry

ResponsePayload: TypeAlias = dict[str, JsonValue]
DedupeKey: TypeAlias = tuple[int, str, str, str | int]


@dataclass(frozen=True, slots=True)
class McpSubmission:
    accepted: bool
    immediate_response: ResponsePayload | None = field(default=None, repr=False)
    notification: bool = False
    reason: str | None = None


@dataclass(slots=True)
class _Inflight:
    fingerprint: str
    future: asyncio.Future[ResponsePayload] = field(repr=False)
    duplicate_waiters: int = 0


@dataclass(frozen=True, slots=True)
class _Completed:
    fingerprint: str
    response: ResponsePayload = field(repr=False)


@dataclass(frozen=True, slots=True)
class _WorkItem:
    key: DedupeKey = field(repr=False)
    fingerprint: str
    request: McpRequest = field(repr=False)


@dataclass(slots=True)
class _GenerationContext:
    generation: int
    response_sink: McpResponseSink = field(repr=False)
    lifecycle_sink: McpLifecycleSink = field(repr=False)
    queue: asyncio.Queue[_WorkItem | None] = field(repr=False)
    worker: asyncio.Task[None] | None = field(default=None, repr=False)
    session_id: str | None = field(default=None, repr=False)
    accepting: bool = True
    inflight: dict[DedupeKey, _Inflight] = field(default_factory=dict, repr=False)
    completed: OrderedDict[DedupeKey, _Completed] = field(default_factory=OrderedDict, repr=False)
    responses_sent: int = 0
    target_grants: dict[int, tuple[str, float]] = field(
        default_factory=dict, repr=False
    )


_TARGET_GRANT_TTL_SECONDS = 120.0
_ID_MUTATING_TOOLS = frozenset(
    {
        "notes.append",
        "notes.update_title",
        "notes.replace_content",
        "notes.convert_type",
        "notes.pin",
        "notes.delete",
        "notes.restore",
        "tags.bind",
    }
)
_ID_READ_TOOLS = frozenset({"notes.get", "ui.open_note"})
_TARGET_PRODUCER_TOOLS = frozenset(
    {
        "notes.resolve",
        "notes.search",
        "notes.list_recent",
        "notes.list_by_tag",
        "notes.list_deleted",
        "notes.list_todos",
        "notes.list_pinned",
        "notes.create",
    }
)


class McpCoordinator:
    """Own all MCP request execution; the WebSocket receiver only calls submit_nowait."""

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        *,
        queue_capacity: int = MCP_REQUEST_QUEUE_CAPACITY,
        dedupe_capacity: int = MCP_DEDUPE_CAPACITY,
        close_timeout_seconds: float = MCP_WORKER_CLOSE_TIMEOUT_SECONDS,
    ) -> None:
        if queue_capacity <= 0:
            raise ValueError("MCP queue capacity must be positive")
        if dedupe_capacity <= 0:
            raise ValueError("MCP dedupe capacity must be positive")
        self._registry = registry or ToolRegistry()
        self._queue_capacity = queue_capacity
        self._dedupe_capacity = dedupe_capacity
        self._close_timeout_seconds = close_timeout_seconds
        self._contexts: dict[int, _GenerationContext] = {}
        self._lifecycle_history: deque[McpLifecycleSummary] = deque(maxlen=64)

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    @property
    def lifecycle_history(self) -> tuple[McpLifecycleSummary, ...]:
        return tuple(self._lifecycle_history)

    @property
    def responses_sent_count(self) -> int:
        return sum(context.responses_sent for context in self._contexts.values())

    @property
    def worker_alive(self) -> bool:
        return any(
            context.worker is not None and not context.worker.done()
            for context in self._contexts.values()
        )

    @property
    def request_queue_size(self) -> int:
        return sum(context.queue.qsize() for context in self._contexts.values())

    @property
    def inflight_request_count(self) -> int:
        return sum(len(context.inflight) for context in self._contexts.values())

    @property
    def dedupe_entry_count(self) -> int:
        return sum(len(context.completed) for context in self._contexts.values())

    @property
    def dedupe_waiter_count(self) -> int:
        return sum(
            inflight.duplicate_waiters
            for context in self._contexts.values()
            for inflight in context.inflight.values()
        )

    @property
    def response_future_count(self) -> int:
        return sum(
            1
            for context in self._contexts.values()
            for inflight in context.inflight.values()
            if not inflight.future.done()
        )

    @property
    def pending_confirmation_count(self) -> int:
        return self._registry.pending_confirmation_count

    async def open_generation(
        self,
        generation: int,
        *,
        response_sink: McpResponseSink,
        lifecycle_sink: McpLifecycleSink,
    ) -> None:
        if generation <= 0:
            raise ValueError("connection generation must be positive")
        previous = self._contexts.get(generation)
        if previous is not None:
            await self.close_generation(generation, "generation_reopened")
        context = _GenerationContext(
            generation=generation,
            response_sink=response_sink,
            lifecycle_sink=lifecycle_sink,
            queue=asyncio.Queue(maxsize=self._queue_capacity),
        )
        context.worker = asyncio.create_task(
            self._worker_loop(context),
            name=f"assistant-mcp-worker-{generation}",
        )
        self._contexts[generation] = context

    def bind_session(self, generation: int, session_id: str) -> bool:
        context = self._contexts.get(generation)
        clean = session_id.strip()
        if context is None or not context.accepting or not clean:
            return False
        if context.session_id is not None and context.session_id != clean:
            return False
        context.session_id = clean
        return True

    def submit_nowait(self, generation: int, session_id: str, payload: object) -> McpSubmission:
        context = self._contexts.get(generation)
        parsed = parse_jsonrpc_payload(payload)
        if isinstance(parsed, McpParseFailure):
            return McpSubmission(
                accepted=False,
                immediate_response=error_response(parsed.request_id, parsed.code, parsed.message),
                reason="parse_failure",
            )
        if isinstance(parsed, McpNotification):
            if parsed.method == "notifications/initialized":
                return McpSubmission(accepted=True, notification=True, reason="initialized")
            return McpSubmission(
                accepted=False,
                notification=True,
                reason="unsupported_notification",
            )
        if context is None or not context.accepting:
            return McpSubmission(
                accepted=False,
                immediate_response=error_response(
                    parsed.request_id,
                    JSONRPC_SERVER_BUSY,
                    "MCP generation is not accepting requests",
                ),
                reason="generation_closed",
            )
        clean_session = session_id.strip()
        if not clean_session or context.session_id != clean_session:
            return McpSubmission(
                accepted=False,
                immediate_response=error_response(
                    parsed.request_id,
                    JSONRPC_INVALID_REQUEST,
                    "MCP session does not match the active generation",
                ),
                reason="session_mismatch",
            )

        key = self._dedupe_key(generation, clean_session, parsed.request_id)
        fingerprint = self._fingerprint(parsed)
        completed = context.completed.get(key)
        if completed is not None:
            if completed.fingerprint != fingerprint:
                return self._conflict(parsed.request_id)
            context.completed.move_to_end(key)
            return McpSubmission(
                accepted=True,
                immediate_response=completed.response,
                reason="completed_duplicate",
            )
        inflight = context.inflight.get(key)
        if inflight is not None:
            if inflight.fingerprint != fingerprint:
                return self._conflict(parsed.request_id)
            if inflight.duplicate_waiters >= MCP_MAX_DUPLICATE_WAITERS:
                return McpSubmission(
                    accepted=False,
                    immediate_response=error_response(
                        parsed.request_id,
                        JSONRPC_SERVER_BUSY,
                        "Too many duplicate MCP waiters",
                    ),
                    reason="duplicate_waiter_overflow",
                )
            inflight.duplicate_waiters += 1
            return McpSubmission(accepted=True, reason="inflight_duplicate")
        if context.queue.full():
            return McpSubmission(
                accepted=False,
                immediate_response=error_response(
                    parsed.request_id,
                    JSONRPC_SERVER_BUSY,
                    "MCP request queue is full",
                ),
                reason="queue_full",
            )
        future: asyncio.Future[ResponsePayload] = asyncio.get_running_loop().create_future()
        context.inflight[key] = _Inflight(fingerprint=fingerprint, future=future)
        context.queue.put_nowait(_WorkItem(key=key, fingerprint=fingerprint, request=parsed))
        return McpSubmission(accepted=True, reason="queued")

    async def close_generation(self, generation: int, reason: str) -> None:
        context = self._contexts.pop(generation, None)
        if context is None:
            return
        context.accepting = False
        await self._registry.close_generation(generation, reason)
        while True:
            try:
                item = context.queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            try:
                if item is not None:
                    inflight = context.inflight.pop(item.key, None)
                    if inflight is not None and not inflight.future.done():
                        inflight.future.set_result(
                            error_response(
                                item.request.request_id,
                                JSONRPC_SERVER_BUSY,
                                "MCP generation closed before execution",
                            )
                        )
            finally:
                context.queue.task_done()
        worker = context.worker
        if worker is not None and not worker.done():
            try:
                context.queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
            try:
                await asyncio.wait_for(worker, timeout=self._close_timeout_seconds)
            except TimeoutError:
                worker.cancel()
                await asyncio.gather(worker, return_exceptions=True)
        for inflight in context.inflight.values():
            if not inflight.future.done():
                inflight.future.cancel()
        context.inflight.clear()
        context.completed.clear()
        await self._registry.close_generation(generation, reason)
        context.session_id = None
        context.worker = None

    async def close(self) -> None:
        for generation in tuple(self._contexts):
            await self.close_generation(generation, "coordinator_close")
        await self._registry.close()

    async def _worker_loop(self, context: _GenerationContext) -> None:
        while True:
            item = await context.queue.get()
            try:
                if item is None:
                    return
                await self._execute_item(context, item)
            finally:
                context.queue.task_done()

    async def _execute_item(self, context: _GenerationContext, item: _WorkItem) -> None:
        started = time.perf_counter_ns()
        request = item.request
        tool_name: str | None = None
        risk: str | None = None
        status = "failed"
        try:
            response, tool_name, risk, status = await self._execute_request(context, request)
        except Exception:
            response = internal_error(request.request_id)
            status = "internal_error"
        inflight = context.inflight.pop(item.key, None)
        duplicate_waiters = inflight.duplicate_waiters if inflight is not None else 0
        if inflight is not None and not inflight.future.done():
            inflight.future.set_result(response)
        context.completed[item.key] = _Completed(item.fingerprint, response)
        context.completed.move_to_end(item.key)
        while len(context.completed) > self._dedupe_capacity:
            context.completed.popitem(last=False)

        response_status = status
        for _ in range(duplicate_waiters + 1):
            try:
                await context.response_sink(response)
                context.responses_sent += 1
            except Exception:
                response_status = f"{status}_response_lost"
                break
        duration_ms = round((time.perf_counter_ns() - started) / 1_000_000, 3)
        summary = McpLifecycleSummary(
            request_id_hash=self._request_id_hash(request.request_id),
            method=request.method,
            tool_name=tool_name,
            status=response_status,
            risk=risk,
            duration_ms=duration_ms,
        )
        self._lifecycle_history.append(summary)
        try:
            await context.lifecycle_sink(summary)
        except Exception:
            # Audit/UI projection failure must not terminate the sole MCP worker.
            pass

    async def _execute_request(
        self, context: _GenerationContext, request: McpRequest
    ) -> tuple[ResponsePayload, str | None, str | None, str]:
        if request.method == "initialize":
            result: dict[str, JsonValue] = {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "serverInfo": {"name": MCP_SERVER_NAME, "version": MCP_SERVER_VERSION},
                "capabilities": {"tools": {"listChanged": False}},
            }
            return success_response(request.request_id, result), None, None, "success"
        if request.method == "tools/list":
            unknown = set(request.params) - {"cursor", "withUserTools"}
            if unknown:
                return invalid_params(request.request_id), None, None, "invalid_params"
            cursor = request.params.get("cursor")
            if cursor is not None and cursor != "":
                return (
                    invalid_params(request.request_id, "Unknown tools/list cursor"),
                    None,
                    None,
                    "invalid_params",
                )
            with_user_tools = request.params.get("withUserTools")
            if with_user_tools is not None and not isinstance(with_user_tools, bool):
                return invalid_params(request.request_id), None, None, "invalid_params"
            result = {"tools": self._registry.public_tools(), "nextCursor": None}
            return success_response(request.request_id, result), None, None, "success"
        if request.method != "tools/call":
            return method_not_found(request.request_id), None, None, "method_not_found"

        unknown = set(request.params) - {"name", "arguments"}
        name = request.params.get("name")
        arguments = request.params.get("arguments", {})
        if unknown or not isinstance(name, str) or not name or not isinstance(arguments, Mapping):
            return invalid_params(request.request_id), None, None, "invalid_params"
        descriptor = self._registry.get(name)
        if descriptor is None:
            return (
                method_not_found(request.request_id, "Tool not found"),
                name,
                None,
                "tool_not_found",
            )
        risk = descriptor.risk.value
        blocked = self._target_provenance_failure(context, name, arguments)
        if blocked is not None:
            result = ToolResult(
                status="blocked",
                message=blocked,
                tool_name=name,
                risk=descriptor.risk,
                error_code="untrusted_note_target",
            )
        else:
            try:
                result = await self._registry.call(
                    ToolCall(
                        request_id=request.request_id,
                        tool_name=name,
                        arguments=dict(arguments),
                        connection_generation=context.generation,
                        session_id=context.session_id,
                    )
                )
            except SchemaValidationError as exc:
                return (
                    invalid_params(request.request_id, str(exc)),
                    name,
                    risk,
                    "invalid_params",
                )
            except KeyError:
                return (
                    method_not_found(request.request_id, "Tool not found"),
                    name,
                    None,
                    "tool_not_found",
                )
            self._update_target_grants(context, name, result)

        result_json = json.dumps(
            result.public_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        if len(result_json.encode("utf-8")) > MCP_MAX_RESULT_BYTES:
            return (
                internal_error(request.request_id, "Tool result exceeds output budget"),
                name,
                risk,
                "result_too_large",
            )
        response = success_response(
            request.request_id,
            {
                "content": [{"type": "text", "text": result_json}],
                "isError": result.status
                not in {"success", "requires_confirmation", "partial_success"},
            },
        )
        return response, name, risk, result.status

    @staticmethod
    def _argument_note_ids(arguments: Mapping[str, object]) -> set[int]:
        values: list[object] = []
        if "note_id" in arguments:
            values.append(arguments.get("note_id"))
        note_ids = arguments.get("note_ids")
        if isinstance(note_ids, list):
            values.extend(note_ids)
        result: set[int] = set()
        for value in values:
            if isinstance(value, bool):
                continue
            try:
                note_id = int(value)
            except (TypeError, ValueError):
                continue
            if note_id > 0:
                result.add(note_id)
        return result

    def _target_provenance_failure(
        self,
        context: _GenerationContext,
        tool_name: str,
        arguments: Mapping[str, object],
    ) -> str | None:
        if tool_name not in _ID_MUTATING_TOOLS | _ID_READ_TOOLS:
            return None
        requested = self._argument_note_ids(arguments)
        now = time.monotonic()
        context.target_grants = {
            note_id: grant
            for note_id, grant in context.target_grants.items()
            if grant[1] >= now
        }
        required = "resolved" if tool_name in _ID_MUTATING_TOOLS else "readable"
        unauthorized = {
            note_id
            for note_id in requested
            if note_id not in context.target_grants
            or (
                required == "resolved"
                and context.target_grants[note_id][0] != "resolved"
            )
        }
        if not requested or unauthorized:
            return "目标尚未按便签标题唯一定位，操作未执行"
        return None

    @staticmethod
    def _update_target_grants(
        context: _GenerationContext, tool_name: str, result: ToolResult
    ) -> None:
        if tool_name in _ID_MUTATING_TOOLS:
            for note_id in result.affected_note_ids:
                context.target_grants.pop(note_id, None)
            return
        if result.status != "success" or tool_name not in _TARGET_PRODUCER_TOOLS:
            return
        affected = set(result.affected_note_ids)
        if not affected:
            return
        payload = result.result if isinstance(result.result, Mapping) else {}
        unique_resolve = (
            tool_name == "notes.resolve"
            and payload.get("resolution_status") == "resolved"
            and len(affected) == 1
        )
        level = "resolved" if unique_resolve else "readable"
        expires_at = time.monotonic() + _TARGET_GRANT_TTL_SECONDS
        for note_id in affected:
            context.target_grants[note_id] = (level, expires_at)

    @staticmethod
    def _fingerprint(request: McpRequest) -> str:
        canonical = json.dumps(
            {"method": request.method, "params": request.params},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _request_id_hash(request_id: RequestId) -> str:
        marker = f"{type(request_id).__name__}:{request_id}".encode("utf-8")
        return hashlib.sha256(marker).hexdigest()[:16]

    @staticmethod
    def _dedupe_key(generation: int, session_id: str, request_id: RequestId) -> DedupeKey:
        return generation, session_id, type(request_id).__name__, request_id

    @staticmethod
    def _conflict(request_id: RequestId) -> McpSubmission:
        return McpSubmission(
            accepted=False,
            immediate_response=error_response(
                request_id,
                JSONRPC_INVALID_REQUEST,
                "Request id was reused with different method or arguments",
            ),
            reason="request_id_conflict",
        )
