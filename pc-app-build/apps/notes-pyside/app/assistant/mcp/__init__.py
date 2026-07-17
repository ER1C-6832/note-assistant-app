"""Gate 5 in-process Xiaozhi MCP protocol runtime."""

from .constants import (
    MCP_DEDUPE_CAPACITY,
    MCP_MAX_OUTER_MESSAGE_BYTES,
    MCP_MAX_RESULT_BYTES,
    MCP_REQUEST_QUEUE_CAPACITY,
)
from .contracts import (
    ConfirmationPolicy,
    McpLifecycleSummary,
    ToolCall,
    ToolDescriptor,
    ToolResult,
    ToolRisk,
)
from .coordinator import McpCoordinator, McpSubmission
from .descriptors import (
    FROZEN_GATE5_TOOL_NAMES,
    GATE5_TOOL_DESCRIPTORS,
    UNSUPPORTED_ANDROID_TOOL_NAMES,
)
from .registry import GateNotReadyExecutor, ToolRegistry
from .router import McpAwareXiaozhiMessageRouter, PrivateMcpEnvelope
from .transport_adapters import McpRealWebSocketTransport, McpScriptedFakeTransport

__all__ = [
    "ConfirmationPolicy",
    "FROZEN_GATE5_TOOL_NAMES",
    "GATE5_TOOL_DESCRIPTORS",
    "GateNotReadyExecutor",
    "MCP_DEDUPE_CAPACITY",
    "MCP_MAX_OUTER_MESSAGE_BYTES",
    "MCP_MAX_RESULT_BYTES",
    "MCP_REQUEST_QUEUE_CAPACITY",
    "McpAwareXiaozhiMessageRouter",
    "McpCoordinator",
    "McpLifecycleSummary",
    "McpRealWebSocketTransport",
    "McpScriptedFakeTransport",
    "McpSubmission",
    "PrivateMcpEnvelope",
    "ToolCall",
    "ToolDescriptor",
    "ToolRegistry",
    "ToolResult",
    "ToolRisk",
    "UNSUPPORTED_ANDROID_TOOL_NAMES",
]
