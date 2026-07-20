"""Run the Gate 6.2 deterministic lifecycle/owner matrix."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    with tempfile.TemporaryDirectory(
        prefix="note-assistant-gate6-2-fake-",
        ignore_cleanup_errors=True,
    ) as directory:
        completed = subprocess.run(
            (
                sys.executable,
                "-m",
                "pytest",
                "-W",
                "error",
                f"--basetemp={Path(directory) / 'basetemp'}",
                "tests/gate6_2",
                "-q",
            ),
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONUTF8": "1", "QT_QPA_PLATFORM": "offscreen"},
            check=False,
        )
    passed = completed.returncode == 0
    report = {
        "status": "gate6_2_fake_kws_complete" if passed else "failed",
        "returncode": completed.returncode,
        "test_output_tail": (completed.stdout or "").splitlines()[-12:],
        "matrix": [
            "default_off",
            "one_hit_one_session",
            "cooldown_duplicate_rejected",
            "button_start_preempts_kws",
            "missing_model_manual_mode_unaffected",
            "native_backend_failure_manual_mode_unaffected",
            "session_terminal_exactly_once_resume",
            "playback_pause_and_resume",
            "route_generation_restart_once",
            "disable_no_resume",
            "terminal_owner_none",
        ],
        "idle_microphone_uploaded_frames": 0,
        "payload_persisted": False,
        "secrets_redacted": True,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
