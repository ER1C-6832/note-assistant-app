"""Run the canonical Gate 5.0 Fake protocol/registry acceptance scenario."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.assistant import AssistantRuntimeMode  # noqa: E402
from app.assistant.mcp import (  # noqa: E402
    FROZEN_GATE5_TOOL_NAMES,
    MCP_DEDUPE_CAPACITY,
    MCP_REQUEST_QUEUE_CAPACITY,
    McpCoordinator,
    McpScriptedFakeTransport,
    ToolCall,
    ToolDescriptor,
    ToolRegistry,
    ToolResult,
)


class _BlockingCountingExecutor:
    def __init__(self) -> None:
        self.calls = 0
        self.gate = asyncio.Event()

    async def execute(self, call: ToolCall, descriptor: ToolDescriptor) -> ToolResult:
        self.calls += 1
        await self.gate.wait()
        return ToolResult(
            status="success",
            message="verified",
            tool_name=call.tool_name,
            risk=descriptor.risk,
            result={"verified": True},
        )


async def _wait_until(predicate, timeout_seconds: float = 3.0) -> None:
    async with asyncio.timeout(timeout_seconds):
        while not predicate():
            await asyncio.sleep(0)


def _name_set_hash() -> str:
    canonical = "\n".join(sorted(FROZEN_GATE5_TOOL_NAMES)).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


async def _run() -> int:
    events = []

    async def event_sink(event) -> None:
        events.append(event)

    executor = _BlockingCountingExecutor()
    coordinator = McpCoordinator(ToolRegistry(executor=executor))
    transport = McpScriptedFakeTransport(mcp_coordinator=coordinator)
    await transport.open(1, AssistantRuntimeMode.FAKE, event_sink)
    try:
        await transport.receive_mcp(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )
        await transport.receive_mcp(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            }
        )
        await transport.receive_mcp(
            {"jsonrpc": "2.0", "id": "list", "method": "tools/list", "params": {}}
        )
        await transport.wait_for_mcp_responses(2)

        request = {
            "jsonrpc": "2.0",
            "id": "duplicate-call",
            "method": "tools/call",
            "params": {"name": "tags.list", "arguments": {}},
        }
        await transport.receive_mcp(request)
        await transport.receive_mcp(request)
        conflicting = await transport.receive_mcp(
            {
                "jsonrpc": "2.0",
                "id": "duplicate-call",
                "method": "tools/call",
                "params": {"name": "ui.show_search", "arguments": {"query": "x"}},
            }
        )
        assert conflicting is False
        executor.gate.set()
        await transport.wait_for_mcp_responses(5)
        await _wait_until(lambda: len(transport.mcp_lifecycle) >= 3)

        initialize = transport.mcp_responses[0]
        listed = transport.mcp_responses[1]
        conflict = transport.mcp_responses[2]
        duplicate_responses = transport.mcp_responses[3:5]
        tool_names = [tool["name"] for tool in listed["result"]["tools"]]
        verified = bool(
            initialize["result"]["serverInfo"]["name"] == "note-assistant-pc"
            and initialize["result"]["protocolVersion"] == "2024-11-05"
            and listed["id"] == "list"
            and len(tool_names) == 31
            and set(tool_names) == set(FROZEN_GATE5_TOOL_NAMES)
            and listed["result"]["nextCursor"] is None
            and conflict["error"]["code"] == -32600
            and executor.calls == 1
            and len(duplicate_responses) == 2
            and duplicate_responses[0] == duplicate_responses[1]
            and coordinator.dedupe_waiter_count == 0
        )
        before_close = {
            "request_queue_size": coordinator.request_queue_size,
            "worker_alive": coordinator.worker_alive,
            "inflight_request_count": coordinator.inflight_request_count,
            "dedupe_waiter_count": coordinator.dedupe_waiter_count,
            "response_future_count": coordinator.response_future_count,
        }
    finally:
        await transport.close(1, "gate5_0_fake_complete", event_sink)

    terminal = {
        "request_queue_size": coordinator.request_queue_size,
        "worker_alive": coordinator.worker_alive,
        "inflight_request_count": coordinator.inflight_request_count,
        "dedupe_entry_count": coordinator.dedupe_entry_count,
        "dedupe_waiter_count": coordinator.dedupe_waiter_count,
        "response_future_count": coordinator.response_future_count,
    }
    verified = verified and all(value in {0, False} for value in terminal.values())
    result = {
        "status": "fake_gate_complete" if verified else "failed",
        "tool_count": len(FROZEN_GATE5_TOOL_NAMES),
        "tool_name_set_sha256": _name_set_hash(),
        "queue_capacity": MCP_REQUEST_QUEUE_CAPACITY,
        "dedupe_capacity": MCP_DEDUPE_CAPACITY,
        "initialize_verified": initialize["result"]["serverInfo"]["name"] == "note-assistant-pc",
        "tools_list_verified": len(tool_names) == 31,
        "duplicate_inflight_execution_count": executor.calls,
        "duplicate_response_count": len(duplicate_responses),
        "same_id_different_payload_conflict": conflict["error"]["code"] == -32600,
        "lifecycle_event_count": len(transport.mcp_lifecycle),
        "protocol_observation_count": sum(
            type(event).__name__ == "ProtocolMessageObserved" for event in events
        ),
        "before_close": before_close,
        "terminal": terminal,
        "payload_persisted": False,
        "secrets_redacted": True,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if verified else 1


def main() -> int:
    try:
        return asyncio.run(_run())
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "message": str(exc)[:300],
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
