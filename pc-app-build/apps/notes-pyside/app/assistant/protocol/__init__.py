"""Xiaozhi protocol builders, routers, and typed wire events."""

from .events import (
    AssistantText,
    BinaryAudio,
    ListenState,
    McpEnvelope,
    ProtocolError,
    ProtocolEvent,
    ServerHello,
    TtsState,
    UnknownJson,
)
from .message_builder import XiaozhiMessageBuilder
from .message_router import XiaozhiMessageRouter, redact_json
from .transcript import (
    has_readable_transcript_text,
    is_terminal_tts_state,
    merge_assistant_transcript,
)

__all__ = [
    "AssistantText",
    "BinaryAudio",
    "ListenState",
    "McpEnvelope",
    "ProtocolError",
    "ProtocolEvent",
    "ServerHello",
    "TtsState",
    "UnknownJson",
    "XiaozhiMessageBuilder",
    "XiaozhiMessageRouter",
    "has_readable_transcript_text",
    "is_terminal_tts_state",
    "merge_assistant_transcript",
    "redact_json",
]
