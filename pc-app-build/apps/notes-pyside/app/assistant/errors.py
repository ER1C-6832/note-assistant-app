"""Stable Assistant Runtime error codes and redaction helpers."""

from __future__ import annotations

import re
from enum import Enum


class AssistantErrorCode(str, Enum):
    """Stable codes consumed by UI, diagnostics, and automated acceptance."""

    ASSISTANT_DISABLED = "assistant_disabled"
    EMPTY_TEXT = "empty_text"
    ASSISTANT_NOT_CONNECTED = "assistant_not_connected"
    TEXT_TURN_IN_PROGRESS = "text_turn_in_progress"
    TRANSPORT_CLOSED_ABNORMALLY = "transport_closed_abnormally"
    TRANSPORT_FAILURE = "transport_failure"
    RECONNECT_EXHAUSTED = "reconnect_exhausted"
    EFFECT_EXECUTION_FAILED = "effect_execution_failed"
    RUNTIME_OVERLOADED = "runtime_overloaded"
    PUSH_TO_TALK_BUSY = "push_to_talk_busy"
    VOICE_MODE_MISMATCH = "voice_mode_mismatch"
    MICROPHONE_PERMISSION_DENIED = "microphone_permission_denied"
    MICROPHONE_BUSY = "microphone_busy"
    AUDIO_CAPTURE_FAILED = "audio_capture_failed"
    AUDIO_ENCODER_FAILED = "audio_encoder_failed"
    AUDIO_UPLINK_FAILED = "audio_uplink_failed"
    AUDIO_UPLINK_OVERFLOW = "audio_uplink_overflow"
    AUDIO_STOP_TIMEOUT = "audio_stop_timeout"
    AUDIO_CAPTURE_STOP_FAILED = "audio_capture_stop_failed"


_SENSITIVE_ERROR_PATTERN = re.compile(
    r"(?i)(bearer\s+)[^\s,;]+|"
    r"((?:token|authorization|hmac|challenge|secret|key)\s*[:=]\s*)[^\s,;&]+|"
    r"([?&](?:token|access_token|auth|key)=)[^&\s]+"
)


def redact_error_text(value: object, *, limit: int = 500) -> str:
    """Return a bounded error string without credential-bearing values."""

    text = str(value) or type(value).__name__

    def replace_sensitive(match: re.Match[str]) -> str:
        prefix = match.group(1) or match.group(2) or match.group(3) or ""
        return f"{prefix}***"

    return _SENSITIVE_ERROR_PATTERN.sub(replace_sensitive, text)[:limit]
