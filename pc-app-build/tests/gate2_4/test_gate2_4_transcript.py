from __future__ import annotations

from app.assistant.protocol import (
    has_readable_transcript_text,
    is_terminal_tts_state,
    merge_assistant_transcript,
)


def test_readable_transcript_filters_status_only_emoji() -> None:
    assert has_readable_transcript_text("你好")
    assert has_readable_transcript_text("Gate 2.4 ready")
    assert not has_readable_transcript_text("😊")
    assert not has_readable_transcript_text("  ")


def test_transcript_merge_deduplicates_streaming_chunks() -> None:
    assert merge_assistant_transcript("你好", "你好") == "你好"
    assert merge_assistant_transcript("你好", "你好，我是小智") == "你好，我是小智"
    assert merge_assistant_transcript("Hello", "world") == "Hello world"
    assert merge_assistant_transcript("小智已经", "经连接") == "小智已经连接"


def test_terminal_tts_states_are_explicit() -> None:
    assert is_terminal_tts_state("stop")
    assert is_terminal_tts_state("END")
    assert not is_terminal_tts_state("sentence_start")
