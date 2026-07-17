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
from .gate5_1_executor import Gate51ToolExecutor, READ_TOOL_NAMES, UI_TOOL_NAMES
from .gate5_2_executor import (
    Gate52ToolExecutor,
    NOTE_MUTATION_TOOL_NAMES,
    TAG_TOOL_NAMES,
)
from .registry import GateNotReadyExecutor, ToolRegistry
from .router import McpAwareXiaozhiMessageRouter, PrivateMcpEnvelope
from .transport_adapters import McpRealWebSocketTransport, McpScriptedFakeTransport
from .ui_bus import (
    UiCommand,
    UiCommandAdapter,
    UiCommandBus,
    UiCommandKind,
    UiDispatchResult,
)

__all__ = [
    "ConfirmationPolicy",
    "FROZEN_GATE5_TOOL_NAMES",
    "GATE5_TOOL_DESCRIPTORS",
    "Gate51ToolExecutor",
    "Gate52ToolExecutor",
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
    "NOTE_MUTATION_TOOL_NAMES",
    "PrivateMcpEnvelope",
    "READ_TOOL_NAMES",
    "TAG_TOOL_NAMES",
    "ToolCall",
    "ToolDescriptor",
    "ToolRegistry",
    "ToolResult",
    "ToolRisk",
    "UI_TOOL_NAMES",
    "UNSUPPORTED_ANDROID_TOOL_NAMES",
    "UiCommand",
    "UiCommandAdapter",
    "UiCommandBus",
    "UiCommandKind",
    "UiDispatchResult",
]
