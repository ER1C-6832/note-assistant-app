from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from app.assistant.mcp.descriptors import FROZEN_GATE5_TOOL_NAMES  # noqa: E402
from gate5_4_acceptance_catalog import GATE5_4_ACCEPTANCE_CASES  # noqa: E402


def test_real_language_catalog_covers_every_frozen_tool_once() -> None:
    names = tuple(case.tool_name for case in GATE5_4_ACCEPTANCE_CASES)
    assert names == FROZEN_GATE5_TOOL_NAMES
    assert len(names) == 31
    assert len(set(names)) == 31
    for case in GATE5_4_ACCEPTANCE_CASES:
        assert case.command.strip()
        assert case.verbose_command.strip()
        assert case.expected.strip()
        assert any("\u4e00" <= char <= "\u9fff" for char in case.command)
        assert any("\u4e00" <= char <= "\u9fff" for char in case.verbose_command)
