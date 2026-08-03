from __future__ import annotations

from app.assistant.mcp.gate5_1_executor import (
    Gate51ToolExecutor,
    _search_result_message,
)


def test_gate51_result_helpers_remain_class_methods() -> None:
    for name in ("_missing_search_terms", "_not_found", "_success"):
        assert callable(getattr(Gate51ToolExecutor, name, None)), name


def test_search_copy_helper_stays_at_module_scope() -> None:
    assert callable(_search_result_message)
    assert "_search_result_message" not in Gate51ToolExecutor.__dict__
