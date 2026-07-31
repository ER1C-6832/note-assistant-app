from __future__ import annotations

import asyncio

from app.assistant.mcp.contracts import ToolCall
from app.assistant.mcp.descriptors import GATE5_TOOL_DESCRIPTORS
from app.assistant.mcp.gate5_1_executor import Gate51ToolExecutor
from app.assistant.mcp.intent_rules import (
    extract_search_terms,
    is_generic_note_search_query,
)

_DESCRIPTOR_MAP = {item.name: item for item in GATE5_TOOL_DESCRIPTORS}


class _FailIfQueried:
    def __getattr__(self, name):
        raise AssertionError(f"query service must not be called: {name}")


def _execute(tool_name: str, arguments: dict):
    executor = Gate51ToolExecutor(_FailIfQueried(), object())
    return asyncio.run(
        executor.execute(
            ToolCall(
                request_id="generic-note-test",
                tool_name=tool_name,
                arguments=arguments,
            ),
            _DESCRIPTOR_MAP[tool_name],
        )
    )


def test_generic_query_normalization_returns_no_terms() -> None:
    for query in (
        "查便签",
        "查一个便签",
        "帮我找一个笔记",
        "随便查一条便签",
    ):
        assert is_generic_note_search_query(query) is True
        assert extract_search_terms(query) == ()

    assert is_generic_note_search_query("查王总报价的便签") is False
    assert extract_search_terms("查王总报价的便签")


def test_notes_search_blocks_missing_semantic_terms_before_database_access() -> None:
    result = _execute("notes.search", {"query": "查一个便签"})
    assert result.status == "blocked"
    assert result.error_code == "missing_search_terms"
    assert result.affected_note_ids == ()


def test_notes_resolve_blocks_generic_target_before_database_access() -> None:
    result = _execute("notes.resolve", {"query": "便签"})
    assert result.status == "blocked"
    assert result.error_code == "missing_search_terms"
    assert result.affected_note_ids == ()
