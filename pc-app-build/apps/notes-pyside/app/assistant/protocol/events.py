"""Pure protocol events returned by the Xiaozhi message router."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DownlinkAudioFormat:
    """Validated public downlink format advertised by ServerHello."""

    codec: str
    sample_rate_hz: int
    channels: int
    frame_duration_ms: float

    def as_public_dict(self) -> dict[str, int | float | str]:
        return {
            "codec": self.codec,
            "sample_rate_hz": self.sample_rate_hz,
            "channels": self.channels,
            "frame_duration_ms": self.frame_duration_ms,
        }


@dataclass(frozen=True, slots=True)
class ProtocolEvent:
    raw_json_redacted: str | None = None


@dataclass(frozen=True, slots=True)
class ServerHello(ProtocolEvent):
    session_id: str = ""
    transport: str | None = None
    audio_format: DownlinkAudioFormat | None = None
    audio_params_error: str | None = None


@dataclass(frozen=True, slots=True)
class AssistantText(ProtocolEvent):
    source_type: str = "text"
    text: str = ""
    session_id: str | None = None


@dataclass(frozen=True, slots=True)
class TtsState(ProtocolEvent):
    state: str = "unknown"
    text: str | None = None
    session_id: str | None = None


@dataclass(frozen=True, slots=True)
class ListenState(ProtocolEvent):
    state: str = "unknown"
    session_id: str | None = None


@dataclass(frozen=True, slots=True)
class McpEnvelope(ProtocolEvent):
    payload_json_redacted: str = "{}"
    session_id: str | None = None


@dataclass(frozen=True, slots=True)
class TokenUsage(ProtocolEvent):
    session_id: str | None = None
    turn_id: str | None = None
    model: str | None = None
    api_call_count: int = 0
    llm_calls_started: int = 0
    tool_call_count: int = 0
    tool_followup_count: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    known_total_tokens: int = 0
    provider_usage_complete: bool = False
    duration_ms: int = 0
    status: str = "unknown"
    budget_enabled: bool = False
    budget_status: str = "unknown"
    budget_reason: str | None = None
    max_total_tokens_per_turn: int = 0
    max_llm_calls_per_turn: int = 0
    max_tool_calls_per_turn: int = 0
    max_output_tokens_per_request: int = 0
    warn_at_percent: int = 0
    output_cap_enforced: bool = False
    budget_profile: str = "default"
    request_route: str = "unknown"
    routing_reason: str | None = None
    available_tool_count: int = 0
    selected_tool_count: int = 0
    selected_tool_schema_chars: int = 0
    max_tools_per_request: int = 0
    max_tool_schema_chars_per_request: int = 0
    max_message_chars_per_request: int = 0


@dataclass(frozen=True, slots=True)
class UnknownJson(ProtocolEvent):
    message_type: str = "unknown"
    session_id: str | None = None


@dataclass(frozen=True, slots=True)
class ProtocolError(ProtocolEvent):
    error: str = "protocol_error"
    raw_text_redacted: str = ""


@dataclass(frozen=True, slots=True)
class BinaryAudio(ProtocolEvent):
    size_bytes: int = 0
