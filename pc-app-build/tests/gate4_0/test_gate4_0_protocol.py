from __future__ import annotations

import json

import pytest

from app.assistant.protocol import (
    DownlinkAudioFormat,
    ServerHello,
    XiaozhiMessageRouter,
)


def _hello(audio_params) -> str:
    return json.dumps(
        {
            "type": "hello",
            "transport": "websocket",
            "session_id": "session-1",
            "audio_params": audio_params,
        }
    )


def test_valid_server_hello_audio_params_are_typed() -> None:
    event = XiaozhiMessageRouter().route_text(
        _hello(
            {
                "format": "opus",
                "sample_rate": 24_000,
                "channels": 1,
                "frame_duration": 20,
                "future_field": "ignored",
            }
        )
    )

    assert isinstance(event, ServerHello)
    assert event.audio_params_error is None
    assert event.audio_format == DownlinkAudioFormat(
        codec="opus",
        sample_rate_hz=24_000,
        channels=1,
        frame_duration_ms=20.0,
    )


def test_missing_audio_params_preserves_hello_but_fails_format_closed() -> None:
    event = XiaozhiMessageRouter().route_text(
        '{"type":"hello","transport":"websocket","session_id":"session-1"}'
    )

    assert isinstance(event, ServerHello)
    assert event.session_id == "session-1"
    assert event.audio_format is None
    assert event.audio_params_error == "missing_audio_params"


@pytest.mark.parametrize(
    ("audio_params", "expected_error"),
    (
        ([], "audio_params_not_object"),
        (
            {"sample_rate": 16_000, "channels": 1, "frame_duration": 20},
            "audio_params_missing_format",
        ),
        (
            {
                "format": "pcm",
                "sample_rate": 16_000,
                "channels": 1,
                "frame_duration": 20,
            },
            "unsupported_downlink_codec:pcm",
        ),
        (
            {"format": "opus", "sample_rate": 0, "channels": 1, "frame_duration": 20},
            "invalid_downlink_sample_rate",
        ),
        (
            {
                "format": "opus",
                "sample_rate": 44_100,
                "channels": 1,
                "frame_duration": 20,
            },
            "unsupported_downlink_sample_rate:44100",
        ),
        (
            {
                "format": "opus",
                "sample_rate": 16_000,
                "channels": 2,
                "frame_duration": 20,
            },
            "unsupported_downlink_channels:2",
        ),
        (
            {
                "format": "opus",
                "sample_rate": 16_000,
                "channels": 1,
                "frame_duration": 15,
            },
            "unsupported_downlink_frame_duration:15",
        ),
    ),
)
def test_invalid_or_unsupported_audio_params_are_explicit(audio_params, expected_error) -> None:
    event = XiaozhiMessageRouter().route_text(_hello(audio_params))

    assert isinstance(event, ServerHello)
    assert event.audio_format is None
    assert event.audio_params_error == expected_error


def test_hello_redaction_does_not_leak_secret_fields() -> None:
    raw = json.dumps(
        {
            "type": "hello",
            "session_id": "session-1",
            "token": "must-not-leak",
            "audio_params": {
                "format": "opus",
                "sample_rate": 16_000,
                "channels": 1,
                "frame_duration": 20,
            },
        }
    )
    event = XiaozhiMessageRouter().route_text(raw)

    assert isinstance(event, ServerHello)
    assert "must-not-leak" not in (event.raw_json_redacted or "")
    assert '"token":"***"' in (event.raw_json_redacted or "")
