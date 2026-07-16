from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_real_stop_runner_extends_watchdog_and_waits_for_physical_progress() -> None:
    runner = (ROOT / "tools" / "verify_gate4_4_real_stop_during_playback.py").read_text(
        encoding="utf-8"
    )

    assert "GATE4_4_RESPONSE_TIMEOUT_SECONDS" in runner
    assert "streaming_response_timeout_ms=int(response_timeout_seconds * 1_000)" in runner
    assert 'playing.error.code == "streaming_response_timeout"' in runner
    assert "timeout_seconds=response_timeout_seconds + 30.0" in runner
    assert "GATE4_4_AUDIBLE_BEFORE_STOP_SECONDS" in runner
    assert "state.audio.played_frames" in runner
    assert "audible_progress_target_frames" in runner
    assert '"ssl"' in runner


def test_playback_watchdog_emits_live_progress_after_output_starts() -> None:
    coordinator = (
        ROOT / "apps" / "notes-pyside" / "app" / "assistant" / "playback" / "coordinator.py"
    ).read_text(encoding="utf-8")

    assert "if metrics.playback_started_at_ns is not None:" in coordinator
    assert "await self._emit_progress()" in coordinator
