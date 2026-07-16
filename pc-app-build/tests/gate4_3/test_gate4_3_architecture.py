from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "apps" / "notes-pyside" / "app" / "assistant"


def test_gate4_3_has_no_payload_or_platform_hot_path_in_reducer() -> None:
    path = APP / "playback" / "two_turn_state_machine.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert "bytes" not in source
    assert "pyaudio" not in source.lower()
    assert "av." not in source.lower()
    assert "subprocess" not in source
    assert "multiprocessing" not in source
    assert not any(isinstance(node, (ast.AsyncFunctionDef, ast.Await)) for node in ast.walk(tree))


def test_top_level_runtime_routes_to_gate4_3_controller() -> None:
    source = (APP / "__init__.py").read_text(encoding="utf-8")
    assert "playback.two_turn_controller" in source
