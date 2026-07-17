from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "apps" / "notes-pyside" / "app" / "assistant"


def test_gate5_0_files_are_in_process_and_bounded() -> None:
    mcp = APP / "mcp"
    required = {
        "constants.py",
        "contracts.py",
        "descriptors.py",
        "validation.py",
        "jsonrpc.py",
        "registry.py",
        "coordinator.py",
        "router.py",
        "transport_adapters.py",
    }
    assert required.issubset({path.name for path in mcp.glob("*.py")})
    all_text = "\n".join(path.read_text(encoding="utf-8") for path in mcp.glob("*.py"))
    assert "multiprocessing" not in all_text
    assert "subprocess" not in all_text
    assert "localhost" not in all_text
    assert "asyncio.Queue(maxsize=self._queue_capacity)" in all_text
    assert "MCP_REQUEST_QUEUE_CAPACITY = 16" in all_text
    assert "MCP_DEDUPE_CAPACITY = 64" in all_text


def test_real_transport_reuses_the_existing_sender_queue() -> None:
    path = APP / "mcp" / "transport_adapters.py"
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    send_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "send"
    ]
    assert send_calls == []
    assert "await self._enqueue_and_wait(active, wire)" in text
    assert "submit_nowait" in text


def test_private_payload_is_not_projected_to_assistant_state() -> None:
    contracts = (APP / "mcp" / "contracts.py").read_text(encoding="utf-8")
    router = (APP / "mcp" / "router.py").read_text(encoding="utf-8")
    adapters = (APP / "mcp" / "transport_adapters.py").read_text(encoding="utf-8")
    assert "field(repr=False)" in contracts
    assert "payload: object = field(default=None, repr=False)" in router
    assert "session_id=None" in adapters
    assert "summary.public_dict()" in adapters
    assert "event.payload" in adapters


def test_assistant_public_real_transport_is_mcp_aware() -> None:
    from app.assistant import RealWebSocketTransport
    from app.assistant.mcp import McpRealWebSocketTransport

    assert RealWebSocketTransport is McpRealWebSocketTransport
    bootstrap = (ROOT / "apps" / "notes-pyside" / "app" / "bootstrap.py").read_text(
        encoding="utf-8"
    )
    assert "from .assistant import (" in bootstrap
    assert "RealWebSocketTransport," in bootstrap
