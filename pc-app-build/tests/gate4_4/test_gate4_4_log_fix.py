from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = ROOT.parent


def test_repository_readme_states_the_current_gate4_scope() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "当前已实现范围不包含 MCP、KWS 或全双工声学插话" in readme


def test_real_stop_runner_extends_the_internal_response_watchdog() -> None:
    runner = (ROOT / "tools" / "verify_gate4_4_real_stop_during_playback.py").read_text(
        encoding="utf-8"
    )

    assert "GATE4_4_RESPONSE_TIMEOUT_SECONDS" in runner
    assert "streaming_response_timeout_ms=int(response_timeout_seconds * 1_000)" in runner
    assert 'playing.error.code == "streaming_response_timeout"' in runner
    assert "timeout_seconds=response_timeout_seconds + 30.0" in runner
