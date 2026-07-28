from __future__ import annotations

import asyncio
import json

import pytest

from app.assistant.mcp import McpCoordinator, ToolRegistry
from app.assistant.mcp.constants import JSONRPC_INVALID_REQUEST, JSONRPC_SERVER_BUSY
from app.assistant.mcp.contracts import ToolCall, ToolDescriptor, ToolResult


class CountingExecutor:
    def __init__(self, gate: asyncio.Event | None = None) -> None:
        self.calls = 0
        self.gate = gate

    async def execute(self, call: ToolCall, descriptor: ToolDescriptor) -> ToolResult:
        self.calls += 1
        if self.gate is not None:
            await self.gate.wait()
        return ToolResult(
            status="success",
            message="ok",
            tool_name=call.tool_name,
            risk=descriptor.risk,
            result={"call_count": self.calls},
        )


class ProvenanceExecutor(CountingExecutor):
    async def execute(self, call: ToolCall, descriptor: ToolDescriptor) -> ToolResult:
        self.calls += 1
        if call.tool_name == "notes.resolve":
            return ToolResult(
                status="success",
                message="resolved",
                tool_name=call.tool_name,
                risk=descriptor.risk,
                affected_note_ids=(7,),
                result={"resolution_status": "resolved", "note_id": 7},
            )
        return ToolResult(
            status="requires_confirmation",
            message="pending",
            tool_name=call.tool_name,
            risk=descriptor.risk,
            requires_confirmation=True,
            affected_note_ids=(7,),
        )


async def _opened(
    *, executor: CountingExecutor | None = None, queue_capacity: int = 16
) -> tuple[McpCoordinator, list[dict], list[dict]]:
    responses: list[dict] = []
    lifecycle: list[dict] = []

    async def response_sink(payload: dict) -> None:
        responses.append(payload)

    async def lifecycle_sink(summary) -> None:
        lifecycle.append(summary.public_dict())

    coordinator = McpCoordinator(ToolRegistry(executor=executor), queue_capacity=queue_capacity)
    await coordinator.open_generation(
        1,
        response_sink=response_sink,
        lifecycle_sink=lifecycle_sink,
    )
    assert coordinator.bind_session(1, "session-1")
    return coordinator, responses, lifecycle


async def _wait_for_count(values: list[object], count: int) -> None:
    async with asyncio.timeout(2.0):
        while len(values) < count:
            await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_protocol_blocks_raw_note_id_until_unique_resolver_grants_it() -> None:
    executor = ProvenanceExecutor()
    coordinator, responses, _lifecycle = await _opened(executor=executor)
    try:
        direct = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "notes.delete", "arguments": {"note_ids": [3]}},
        }
        assert coordinator.submit_nowait(1, "session-1", direct).accepted
        await _wait_for_count(responses, 1)
        blocked = json.loads(responses[-1]["result"]["content"][0]["text"])
        assert blocked["status"] == "blocked"
        assert blocked["error_code"] == "untrusted_note_target"
        assert executor.calls == 0

        resolve = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "notes.resolve",
                "arguments": {"exact_title": "3"},
            },
        }
        assert coordinator.submit_nowait(1, "session-1", resolve).accepted
        await _wait_for_count(responses, 2)

        wrong = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "notes.delete", "arguments": {"note_ids": [3]}},
        }
        assert coordinator.submit_nowait(1, "session-1", wrong).accepted
        await _wait_for_count(responses, 3)
        assert json.loads(responses[-1]["result"]["content"][0]["text"])[
            "status"
        ] == "blocked"

        trusted = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "notes.delete", "arguments": {"note_ids": [7]}},
        }
        assert coordinator.submit_nowait(1, "session-1", trusted).accepted
        await _wait_for_count(responses, 4)
        pending = json.loads(responses[-1]["result"]["content"][0]["text"])
        assert pending["status"] == "requires_confirmation"
        assert executor.calls == 2
    finally:
        await coordinator.close()


@pytest.mark.asyncio
async def test_initialize_list_and_not_ready_call() -> None:
    coordinator, responses, lifecycle = await _opened()
    try:
        assert coordinator.submit_nowait(
            1,
            "session-1",
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        ).accepted
        assert coordinator.submit_nowait(
            1,
            "session-1",
            {"jsonrpc": "2.0", "id": "list", "method": "tools/list", "params": {}},
        ).accepted
        assert coordinator.submit_nowait(
            1,
            "session-1",
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "tags.list", "arguments": {}},
            },
        ).accepted
        await _wait_for_count(responses, 3)

        initialize = responses[0]
        assert initialize["id"] == 1
        assert initialize["result"]["serverInfo"]["name"] == "note-assistant-pc"
        listed = responses[1]
        assert listed["id"] == "list"
        assert len(listed["result"]["tools"]) == 32
        assert listed["result"]["nextCursor"] is None
        call = responses[2]
        text = call["result"]["content"][0]["text"]
        result = json.loads(text)
        assert result["status"] == "blocked"
        assert result["error_code"] == "gate_not_ready"
        assert call["result"]["isError"] is True
        assert len(lifecycle) == 3
    finally:
        await coordinator.close()
    assert coordinator.worker_alive is False
    assert coordinator.request_queue_size == 0
    assert coordinator.inflight_request_count == 0
    assert coordinator.response_future_count == 0


@pytest.mark.asyncio
async def test_duplicate_inflight_executes_once_and_returns_twice() -> None:
    gate = asyncio.Event()
    executor = CountingExecutor(gate)
    coordinator, responses, _ = await _opened(executor=executor)
    request = {
        "jsonrpc": "2.0",
        "id": "same",
        "method": "tools/call",
        "params": {"name": "tags.list", "arguments": {}},
    }
    try:
        first = coordinator.submit_nowait(1, "session-1", request)
        duplicate = coordinator.submit_nowait(1, "session-1", request)
        assert first.accepted and duplicate.accepted
        assert duplicate.reason == "inflight_duplicate"
        gate.set()
        await _wait_for_count(responses, 2)
        assert executor.calls == 1
        assert responses[0] == responses[1]
        assert coordinator.dedupe_waiter_count == 0
    finally:
        await coordinator.close()


@pytest.mark.asyncio
async def test_same_id_different_arguments_is_conflict_with_zero_second_execution() -> None:
    gate = asyncio.Event()
    executor = CountingExecutor(gate)
    coordinator, responses, _ = await _opened(executor=executor)
    first = {
        "jsonrpc": "2.0",
        "id": 9,
        "method": "tools/call",
        "params": {"name": "tags.list", "arguments": {}},
    }
    conflicting = {
        "jsonrpc": "2.0",
        "id": 9,
        "method": "tools/call",
        "params": {"name": "ui.show_search", "arguments": {"query": "x"}},
    }
    try:
        assert coordinator.submit_nowait(1, "session-1", first).accepted
        conflict = coordinator.submit_nowait(1, "session-1", conflicting)
        assert conflict.accepted is False
        assert conflict.immediate_response is not None
        assert conflict.immediate_response["error"]["code"] == JSONRPC_INVALID_REQUEST
        responses.append(conflict.immediate_response)
        gate.set()
        await _wait_for_count(responses, 2)
        assert executor.calls == 1
    finally:
        await coordinator.close()


@pytest.mark.asyncio
async def test_notification_has_no_response_and_unknown_notification_does_not_execute() -> None:
    executor = CountingExecutor()
    coordinator, responses, _ = await _opened(executor=executor)
    try:
        initialized = coordinator.submit_nowait(
            1,
            "session-1",
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            },
        )
        unknown = coordinator.submit_nowait(
            1,
            "session-1",
            {"jsonrpc": "2.0", "method": "tools/call", "params": {}},
        )
        assert initialized.notification and initialized.immediate_response is None
        assert unknown.notification and unknown.accepted is False
        await asyncio.sleep(0)
        assert responses == []
        assert executor.calls == 0
    finally:
        await coordinator.close()


@pytest.mark.asyncio
async def test_queue_overflow_is_immediate_server_busy_and_receiver_never_waits_handler() -> None:
    gate = asyncio.Event()
    executor = CountingExecutor(gate)
    coordinator, responses, _ = await _opened(executor=executor, queue_capacity=1)
    request1 = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "tags.list", "arguments": {}},
    }
    request2 = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "tags.list", "arguments": {}},
    }
    try:
        assert coordinator.submit_nowait(1, "session-1", request1).accepted
        overflow = coordinator.submit_nowait(1, "session-1", request2)
        assert overflow.accepted is False
        assert overflow.reason == "queue_full"
        assert overflow.immediate_response["error"]["code"] == JSONRPC_SERVER_BUSY
        assert executor.calls == 0
        gate.set()
        await _wait_for_count(responses, 1)
    finally:
        await coordinator.close()


@pytest.mark.asyncio
async def test_unknown_tool_and_invalid_schema_never_execute_handler() -> None:
    executor = CountingExecutor()
    coordinator, responses, _ = await _opened(executor=executor)
    try:
        assert coordinator.submit_nowait(
            1,
            "session-1",
            {
                "jsonrpc": "2.0",
                "id": 30,
                "method": "tools/call",
                "params": {"name": "notes.unknown", "arguments": {}},
            },
        ).accepted
        assert coordinator.submit_nowait(
            1,
            "session-1",
            {
                "jsonrpc": "2.0",
                "id": 31,
                "method": "tools/call",
                "params": {"name": "notes.create", "arguments": {}},
            },
        ).accepted
        await _wait_for_count(responses, 2)
        assert responses[0]["error"]["code"] == -32601
        assert responses[1]["error"]["code"] == -32602
        assert executor.calls == 0
    finally:
        await coordinator.close()


@pytest.mark.asyncio
async def test_completed_duplicate_uses_cached_response_and_typed_ids_are_distinct() -> None:
    executor = CountingExecutor()
    coordinator, responses, _ = await _opened(executor=executor)
    integer_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "tags.list", "arguments": {}},
    }
    string_request = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "tools/call",
        "params": {"name": "tags.list", "arguments": {}},
    }
    try:
        assert coordinator.submit_nowait(1, "session-1", integer_request).accepted
        await _wait_for_count(responses, 1)
        cached = coordinator.submit_nowait(1, "session-1", integer_request)
        assert cached.accepted and cached.reason == "completed_duplicate"
        assert cached.immediate_response == responses[0]
        assert coordinator.submit_nowait(1, "session-1", string_request).accepted
        await _wait_for_count(responses, 2)
        assert executor.calls == 2
        assert responses[0]["id"] == 1 and type(responses[0]["id"]) is int
        assert responses[1]["id"] == "1" and type(responses[1]["id"]) is str
    finally:
        await coordinator.close()


@pytest.mark.asyncio
async def test_dedupe_cache_is_bounded_and_evicted_request_can_execute_again() -> None:
    executor = CountingExecutor()
    responses: list[dict] = []

    async def response_sink(payload: dict) -> None:
        responses.append(payload)

    async def lifecycle_sink(_summary) -> None:
        return None

    coordinator = McpCoordinator(ToolRegistry(executor=executor), dedupe_capacity=2)
    await coordinator.open_generation(1, response_sink=response_sink, lifecycle_sink=lifecycle_sink)
    coordinator.bind_session(1, "session-1")
    try:
        for request_id in (1, 2, 3):
            assert coordinator.submit_nowait(
                1,
                "session-1",
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": "tools/call",
                    "params": {"name": "tags.list", "arguments": {}},
                },
            ).accepted
        await _wait_for_count(responses, 3)
        assert coordinator.dedupe_entry_count == 2
        assert coordinator.submit_nowait(
            1,
            "session-1",
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "tags.list", "arguments": {}},
            },
        ).accepted
        await _wait_for_count(responses, 4)
        assert executor.calls == 4
        assert coordinator.dedupe_entry_count == 2
    finally:
        await coordinator.close()


@pytest.mark.asyncio
async def test_close_cancels_a_stuck_worker_and_clears_all_private_state() -> None:
    gate = asyncio.Event()
    executor = CountingExecutor(gate)
    responses: list[dict] = []

    async def response_sink(payload: dict) -> None:
        responses.append(payload)

    async def lifecycle_sink(_summary) -> None:
        return None

    coordinator = McpCoordinator(ToolRegistry(executor=executor), close_timeout_seconds=0.01)
    await coordinator.open_generation(1, response_sink=response_sink, lifecycle_sink=lifecycle_sink)
    coordinator.bind_session(1, "session-1")
    assert coordinator.submit_nowait(
        1,
        "session-1",
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "tags.list", "arguments": {}},
        },
    ).accepted
    await asyncio.sleep(0)
    assert executor.calls == 1
    await coordinator.close_generation(1, "test_close")
    assert coordinator.worker_alive is False
    assert coordinator.request_queue_size == 0
    assert coordinator.inflight_request_count == 0
    assert coordinator.dedupe_entry_count == 0
    assert coordinator.dedupe_waiter_count == 0
    assert coordinator.response_future_count == 0
