"""Fail-closed Xiaozhi text and binary message router."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from .events import (
    AssistantText,
    BinaryAudio,
    DownlinkAudioFormat,
    ListenState,
    McpEnvelope,
    ProtocolError,
    ProtocolEvent,
    ServerHello,
    TokenUsage,
    TtsState,
    UnknownJson,
)

_SENSITIVE_KEYS = {
    "authorization",
    "token",
    "access_token",
    "websocket_token",
    "hmac",
    "hmac_key",
    "challenge",
    "secret",
    "password",
}
_SUPPORTED_OPUS_SAMPLE_RATES = {8_000, 12_000, 16_000, 24_000, 48_000}
_SUPPORTED_OPUS_FRAME_DURATIONS_MS = {2.5, 5.0, 10.0, 20.0, 40.0, 60.0}


class XiaozhiMessageRouter:
    """Convert untrusted wire messages into typed protocol events without throwing."""

    def route_text(self, raw: str) -> ProtocolEvent:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            return ProtocolError(
                error=f"invalid_json:{exc.msg}",
                raw_text_redacted=f"<invalid-json chars={len(raw)}>",
            )

        if not isinstance(payload, dict):
            return ProtocolError(
                error="json_root_not_object",
                raw_text_redacted=f"<json-{type(payload).__name__}>",
            )

        redacted = redact_json(payload)
        message_type = _text(payload.get("type"))
        if not message_type and _text(payload.get("method")):
            message_type = "mcp"
        if not message_type:
            return ProtocolError(
                error="missing_type",
                raw_text_redacted=redacted,
                raw_json_redacted=redacted,
            )

        session_id = _optional_text(payload.get("session_id"))
        if message_type == "hello":
            audio_format, audio_params_error = _parse_audio_params(payload.get("audio_params"))
            return ServerHello(
                session_id=session_id or "",
                transport=_optional_text(payload.get("transport")),
                audio_format=audio_format,
                audio_params_error=audio_params_error,
                raw_json_redacted=redacted,
            )
        if message_type in {"stt", "llm", "text"}:
            text = _text(payload.get("text"))
            if not text:
                return ProtocolError(
                    error="assistant_text_missing_text",
                    raw_text_redacted=redacted,
                    raw_json_redacted=redacted,
                )
            return AssistantText(
                source_type=message_type,
                text=text,
                session_id=session_id,
                raw_json_redacted=redacted,
            )
        if message_type == "tts":
            return TtsState(
                state=_text(payload.get("state")) or "unknown",
                text=_optional_text(payload.get("text")),
                session_id=session_id,
                raw_json_redacted=redacted,
            )
        if message_type == "listen":
            return ListenState(
                state=_text(payload.get("state")) or "unknown",
                session_id=session_id,
                raw_json_redacted=redacted,
            )
        if message_type == "mcp":
            mcp_payload = payload.get("payload")
            if isinstance(mcp_payload, dict):
                redacted_payload = redact_json(mcp_payload)
            elif isinstance(mcp_payload, str) and mcp_payload.strip():
                redacted_payload = _redact_string_payload(mcp_payload)
            elif _text(payload.get("method")):
                redacted_payload = redacted
            else:
                return ProtocolError(
                    error="missing_mcp_payload",
                    raw_text_redacted=redacted,
                    raw_json_redacted=redacted,
                )
            return McpEnvelope(
                payload_json_redacted=redacted_payload,
                session_id=session_id,
                raw_json_redacted=redacted,
            )
        if message_type == "token_usage":
            usage = payload.get("usage")
            if not isinstance(usage, Mapping):
                return ProtocolError(
                    error="token_usage_missing_usage",
                    raw_text_redacted=redacted,
                    raw_json_redacted=redacted,
                )
            integer_fields = (
                "api_call_count",
                "llm_calls_started",
                "tool_call_count",
                "tool_followup_count",
                "known_total_tokens",
                "duration_ms",
                "max_total_tokens_per_turn",
                "max_llm_calls_per_turn",
                "max_tool_calls_per_turn",
                "max_output_tokens_per_request",
                "warn_at_percent",
            )
            optional_integer_fields = (
                "input_tokens",
                "output_tokens",
                "total_tokens",
            )
            normalized_integers: dict[str, int] = {}
            normalized_optional: dict[str, int | None] = {}
            for field in integer_fields:
                value = usage.get(field, 0)
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    return ProtocolError(
                        error=f"token_usage_invalid_{field}",
                        raw_text_redacted=redacted,
                        raw_json_redacted=redacted,
                    )
                normalized_integers[field] = value
            for field in optional_integer_fields:
                value = usage.get(field)
                if value is not None and (
                    isinstance(value, bool) or not isinstance(value, int) or value < 0
                ):
                    return ProtocolError(
                        error=f"token_usage_invalid_{field}",
                        raw_text_redacted=redacted,
                        raw_json_redacted=redacted,
                    )
                normalized_optional[field] = value
            for field in (
                "provider_usage_complete",
                "budget_enabled",
                "output_cap_enforced",
            ):
                if not isinstance(usage.get(field, False), bool):
                    return ProtocolError(
                        error=f"token_usage_invalid_{field}",
                        raw_text_redacted=redacted,
                        raw_json_redacted=redacted,
                    )
            return TokenUsage(
                session_id=session_id,
                turn_id=_optional_limited_text(usage.get("turn_id")),
                model=_optional_limited_text(usage.get("model")),
                status=_limited_text(usage.get("status"), "unknown"),
                budget_status=_limited_text(
                    usage.get("budget_status"), "unknown"
                ),
                budget_reason=_optional_limited_text(usage.get("budget_reason")),
                provider_usage_complete=usage.get(
                    "provider_usage_complete", False
                ),
                budget_enabled=usage.get("budget_enabled", False),
                output_cap_enforced=usage.get("output_cap_enforced", False),
                raw_json_redacted=redacted,
                **normalized_integers,
                **normalized_optional,
            )
        return UnknownJson(
            message_type=message_type,
            session_id=session_id,
            raw_json_redacted=redacted,
        )

    def route_binary(self, data: bytes) -> BinaryAudio:
        return BinaryAudio(size_bytes=len(data))


def _parse_audio_params(value: object) -> tuple[DownlinkAudioFormat | None, str | None]:
    if value is None:
        return None, "missing_audio_params"
    if not isinstance(value, Mapping):
        return None, "audio_params_not_object"

    codec = (_text(value.get("format")) or _text(value.get("codec"))).lower()
    if not codec:
        return None, "audio_params_missing_format"
    if codec != "opus":
        return None, f"unsupported_downlink_codec:{codec}"

    sample_rate = value.get("sample_rate")
    if isinstance(sample_rate, bool) or not isinstance(sample_rate, int) or sample_rate <= 0:
        return None, "invalid_downlink_sample_rate"
    if sample_rate not in _SUPPORTED_OPUS_SAMPLE_RATES:
        return None, f"unsupported_downlink_sample_rate:{sample_rate}"

    channels = value.get("channels")
    if isinstance(channels, bool) or not isinstance(channels, int) or channels <= 0:
        return None, "invalid_downlink_channels"
    if channels != 1:
        return None, f"unsupported_downlink_channels:{channels}"

    frame_duration = value.get("frame_duration")
    if isinstance(frame_duration, bool) or not isinstance(frame_duration, (int, float)):
        return None, "invalid_downlink_frame_duration"
    normalized_duration = float(frame_duration)
    if normalized_duration not in _SUPPORTED_OPUS_FRAME_DURATIONS_MS:
        return None, f"unsupported_downlink_frame_duration:{normalized_duration:g}"

    return (
        DownlinkAudioFormat(
            codec=codec,
            sample_rate_hz=sample_rate,
            channels=channels,
            frame_duration_ms=normalized_duration,
        ),
        None,
    )


def redact_json(payload: Mapping[str, object]) -> str:
    """Return compact JSON with secret-bearing fields replaced recursively."""

    return json.dumps(
        _redact_value(payload),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _redact_value(value: object) -> object:
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, item in value.items():
            key_text = str(key)
            result[key_text] = "***" if key_text.lower() in _SENSITIVE_KEYS else _redact_value(item)
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_redact_value(item) for item in value]
    return value


def _redact_string_payload(raw: str) -> str:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return f"<mcp-string chars={len(raw)}>"
    if isinstance(payload, dict):
        return redact_json(payload)
    return f"<mcp-{type(payload).__name__}>"


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _optional_text(value: object) -> str | None:
    cleaned = _text(value)
    return cleaned or None


def _limited_text(value: object, default: str) -> str:
    cleaned = _text(value)
    return cleaned[:128] if cleaned else default


def _optional_limited_text(value: object) -> str | None:
    cleaned = _text(value)
    return cleaned[:128] if cleaned else None
