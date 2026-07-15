from __future__ import annotations

import json

from app.assistant.protocol import (
    AssistantText,
    BinaryAudio,
    ProtocolError,
    ServerHello,
    UnknownJson,
    XiaozhiMessageBuilder,
    XiaozhiMessageRouter,
)


def test_builder_matches_android_hello_and_text_contract() -> None:
    builder = XiaozhiMessageBuilder()

    hello = json.loads(builder.hello())
    assert hello == {
        "type": "hello",
        "version": 1,
        "features": {"mcp": True},
        "transport": "websocket",
        "audio_params": {
            "format": "opus",
            "sample_rate": 16_000,
            "channels": 1,
            "frame_duration": 20,
        },
    }
    assert json.loads(builder.listen_detect("session-1", '你好 "小智"')) == {
        "session_id": "session-1",
        "type": "listen",
        "state": "detect",
        "text": '你好 "小智"',
    }


def test_router_returns_typed_events_and_redacts_secrets() -> None:
    router = XiaozhiMessageRouter()

    hello = router.route_text(
        '{"type":"hello","transport":"websocket","session_id":"real-session"}'
    )
    assert isinstance(hello, ServerHello)
    assert hello.session_id == "real-session"

    text = router.route_text('{"type":"llm","session_id":"real-session","text":"真实回复"}')
    assert isinstance(text, AssistantText)
    assert text.source_type == "llm"
    assert text.text == "真实回复"

    unknown = router.route_text(
        '{"type":"future_type","token":"raw-secret","session_id":"real-session"}'
    )
    assert isinstance(unknown, UnknownJson)
    assert "raw-secret" not in (unknown.raw_json_redacted or "")
    assert '"token":"***"' in (unknown.raw_json_redacted or "")

    missing_text = router.route_text(
        '{"type":"llm","token":"must-not-leak","session_id":"real-session"}'
    )
    assert isinstance(missing_text, ProtocolError)
    assert missing_text.error == "assistant_text_missing_text"
    assert "must-not-leak" not in missing_text.raw_text_redacted

    invalid = router.route_text("{not-json")
    assert isinstance(invalid, ProtocolError)
    assert "not-json" not in invalid.raw_text_redacted

    binary = router.route_binary(b"\x00\x01\x02")
    assert isinstance(binary, BinaryAudio)
    assert binary.size_bytes == 3
