"""Verify Gate 5.4's frozen tool surface and intent-routing rules."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.assistant.mcp.descriptors import (  # noqa: E402
    FROZEN_GATE5_TOOL_NAMES,
    GATE5_TOOL_DESCRIPTORS,
    UNSUPPORTED_ANDROID_TOOL_NAMES,
)
from app.assistant.mcp.intent_rules import (  # noqa: E402
    TOOL_INTENT_DESCRIPTIONS,
    extract_explicit_note_id,
    extract_search_terms,
    is_contextual_reference,
)
from gate5_4_acceptance_catalog import GATE5_4_ACCEPTANCE_CASES  # noqa: E402

EXPECTED_NAME_SET_SHA256 = "543129cc3d6c8fae161ddb716f6cdbf803920ba8fa674d6c5cf6571a198a10e9"


def main() -> int:
    names = tuple(FROZEN_GATE5_TOOL_NAMES)
    digest = hashlib.sha256("\n".join(sorted(names)).encode()).hexdigest()
    public_tools = [descriptor.public_dict() for descriptor in GATE5_TOOL_DESCRIPTORS]
    serialized_bytes = len(json.dumps(public_tools, ensure_ascii=False).encode("utf-8"))
    descriptions_complete = set(TOOL_INTENT_DESCRIPTIONS) == set(names) and all(
        descriptor.description == TOOL_INTENT_DESCRIPTIONS[descriptor.name]
        and any("\u4e00" <= char <= "\u9fff" for char in descriptor.description)
        for descriptor in GATE5_TOOL_DESCRIPTORS
    )
    samples = {
        "verbose_quote": extract_search_terms("麻烦帮我找一下那个关于王总报价的便签"),
        "verbose_packaging": extract_search_terms("请在小智便签里查查我之前记的包装问题"),
        "verbose_disjunction": extract_search_terms(
            "麻烦帮我看看以前在小智便签里有没有记过包装尺寸或者包装问题，最多给我五条"
        ),
        "explicit_id": extract_explicit_note_id("麻烦读取编号为 12 的便签"),
        "bare_numeric_id": extract_explicit_note_id("119"),
        "numeric_title_terms": extract_search_terms("标题叫119的便签"),
        "contextual": is_contextual_reference("刚才那条便签"),
    }
    catalog_names = tuple(case.tool_name for case in GATE5_4_ACCEPTANCE_CASES)
    verified = all(
        (
            len(names) == 32,
            len(set(names)) == 32,
            digest == EXPECTED_NAME_SET_SHA256,
            not (set(names) & UNSUPPORTED_ANDROID_TOOL_NAMES),
            serialized_bytes < 64 * 1024,
            descriptions_complete,
            catalog_names == names,
            samples["verbose_quote"] == ("王总报价",),
            samples["verbose_packaging"] == ("包装问题",),
            "包装尺寸" in samples["verbose_disjunction"],
            "包装问题" in samples["verbose_disjunction"],
            samples["explicit_id"] == 12,
            samples["bare_numeric_id"] is None,
            samples["numeric_title_terms"][0] == "119",
            samples["contextual"] is True,
        )
    )
    print(
        json.dumps(
            {
                "status": "gate5_4_freeze_complete" if verified else "failed",
                "tool_count": len(names),
                "tool_name_set_sha256": digest,
                "serialized_tools_list_bytes": serialized_bytes,
                "description_coverage": len(TOOL_INTENT_DESCRIPTIONS),
                "acceptance_case_count": len(GATE5_4_ACCEPTANCE_CASES),
                "unsupported_android_tools_advertised": sorted(
                    set(names) & UNSUPPORTED_ANDROID_TOOL_NAMES
                ),
                "normalization_samples": samples,
                "payload_persisted": False,
                "secrets_redacted": True,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
