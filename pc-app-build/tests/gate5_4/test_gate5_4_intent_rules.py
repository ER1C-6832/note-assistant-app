from __future__ import annotations

import hashlib
import json

from app.assistant.mcp.descriptors import (
    FROZEN_GATE5_TOOL_NAMES,
    GATE5_TOOL_DESCRIPTORS,
    UNSUPPORTED_ANDROID_TOOL_NAMES,
)
from app.assistant.mcp.intent_rules import (
    TOOL_INTENT_DESCRIPTIONS,
    extract_explicit_note_id,
    extract_search_terms,
    is_contextual_reference,
)

EXPECTED_NAME_SET_SHA256 = "543129cc3d6c8fae161ddb716f6cdbf803920ba8fa674d6c5cf6571a198a10e9"


def test_frozen_32_tool_name_set_and_descriptor_budget() -> None:
    assert len(FROZEN_GATE5_TOOL_NAMES) == 32
    assert len(set(FROZEN_GATE5_TOOL_NAMES)) == 32
    assert not (set(FROZEN_GATE5_TOOL_NAMES) & UNSUPPORTED_ANDROID_TOOL_NAMES)
    digest = hashlib.sha256("\n".join(sorted(FROZEN_GATE5_TOOL_NAMES)).encode()).hexdigest()
    assert digest == EXPECTED_NAME_SET_SHA256

    payload = [descriptor.public_dict() for descriptor in GATE5_TOOL_DESCRIPTORS]
    assert len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) < 64 * 1024


def test_every_tool_has_chinese_intent_routing_guidance() -> None:
    assert set(TOOL_INTENT_DESCRIPTIONS) == set(FROZEN_GATE5_TOOL_NAMES)
    for descriptor in GATE5_TOOL_DESCRIPTORS:
        assert descriptor.description == TOOL_INTENT_DESCRIPTIONS[descriptor.name]
        assert any("\u4e00" <= char <= "\u9fff" for char in descriptor.description)
        assert len(descriptor.description) >= 24

    assert "不能猜" in TOOL_INTENT_DESCRIPTIONS["notes.resolve"]
    assert "单独的‘119’" in TOOL_INTENT_DESCRIPTIONS["notes.resolve"]
    assert "ui.show_todos" in TOOL_INTENT_DESCRIPTIONS
    assert "不是文件" in TOOL_INTENT_DESCRIPTIONS["notes.search"]
    assert (
        "先调用 assistant.list_pending_confirmations"
        in TOOL_INTENT_DESCRIPTIONS["assistant.confirm"]
    )
    assert "目标含糊" in TOOL_INTENT_DESCRIPTIONS["notes.delete"]


def test_verbose_spoken_query_normalization_is_deterministic() -> None:
    assert extract_search_terms("麻烦帮我找一下那个关于王总报价的便签") == ("王总报价",)
    assert extract_search_terms("请在小智便签里查查我之前记的包装问题") == ("包装问题",)
    verbose_terms = extract_search_terms(
        "麻烦帮我看看以前在小智便签里有没有记过包装尺寸或者包装问题，最多给我五条"
    )
    assert "包装尺寸" in verbose_terms
    assert "包装问题" in verbose_terms
    assert extract_search_terms("打开“客户报价”那条便签")[0] == "客户报价"
    assert extract_search_terms("帮我找一下会议记录") == ("会议记录",)
    assert extract_explicit_note_id("麻烦读取编号为 12 的便签") == 12
    assert extract_explicit_note_id("打开第3号笔记") == 3
    assert extract_explicit_note_id("编号 3 和编号 4") is None
    assert extract_explicit_note_id("119") is None
    assert extract_search_terms("标题叫119的便签")[0] == "119"
    assert is_contextual_reference("刚才那条便签") is True
    assert is_contextual_reference("那个关于包装的便签") is False
