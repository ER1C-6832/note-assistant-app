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
