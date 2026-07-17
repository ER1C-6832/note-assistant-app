from __future__ import annotations

import asyncio

import pytest

from app.assistant import AssistantRuntimeMode
from app.assistant.mcp import McpScriptedFakeTransport


@pytest.mark.asyncio
async def test_fake_transport_uses_real_registry_coordinator_and_cleans_up() -> None:
    events = []

    async def event_sink(event) -> None:
        events.append(event)

    transport = McpScriptedFakeTransport()
    await transport.open(1, AssistantRuntimeMode.FAKE, event_sink)
    assert transport.session_id

    assert await transport.receive_mcp(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    )
    assert await transport.receive_mcp(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    )
    assert await transport.receive_mcp(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "tags.list", "arguments": {}},
        }
    )
    responses = await transport.wait_for_mcp_responses(3)
    assert responses[0]["result"]["serverInfo"]["name"] == "note-assistant-pc"
    assert len(responses[1]["result"]["tools"]) == 32
    assert responses[2]["result"]["isError"] is True
    async with asyncio.timeout(2.0):
        while len(transport.mcp_lifecycle) < 3:
            await asyncio.sleep(0)
    assert any(type(event).__name__ == "ProtocolMessageObserved" for event in events)

    await transport.close(1, "gate5_0_test_complete", event_sink)
    assert transport.mcp_coordinator.worker_alive is False
    assert transport.mcp_coordinator.request_queue_size == 0
    assert transport.mcp_coordinator.inflight_request_count == 0
    assert transport.mcp_coordinator.response_future_count == 0


@pytest.mark.asyncio
async def test_fake_transport_rejects_oversized_outer_message_before_execution() -> None:
    events = []

    async def event_sink(event) -> None:
        events.append(event)

    transport = McpScriptedFakeTransport()
    await transport.open(1, AssistantRuntimeMode.FAKE, event_sink)
    try:
        accepted = await transport.receive_mcp(
            {
                "jsonrpc": "2.0",
                "id": 99,
                "method": "tools/call",
                "params": {
                    "name": "notes.create",
                    "arguments": {"title": "x" * (70 * 1024)},
                },
            }
        )
        assert accepted is False
        responses = await transport.wait_for_mcp_responses(1)
        assert responses[0]["error"]["code"] == -32600
        assert transport.mcp_coordinator.inflight_request_count == 0
    finally:
        await transport.close(1, "oversized_test_complete", event_sink)
