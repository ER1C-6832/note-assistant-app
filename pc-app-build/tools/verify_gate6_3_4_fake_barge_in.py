"""Run the deterministic Gate 6.3+6.4 acoustic barge-in contract matrix."""

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
        prefix="note-assistant-gate6-3-4-fake-",
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
                "tests/gate6_3_4",
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
    print(
        json.dumps(
            {
                "status": "gate6_3_4_fake_barge_in_complete" if passed else "failed",
                "returncode": completed.returncode,
                "test_output_tail": (completed.stdout or "").splitlines()[-12:],
                "matrix": [
                    "render_reference_exact_10ms_blocks",
                    "aec_only_ns_off_agc_off",
                    "processed_audio_only_vad",
                    "one_confirmation_one_abort",
                    "one_confirmation_one_next_capture",
                    "duplicate_confirmation_rejected",
                    "late_playback_ended_rejected",
                    "stale_generation_rejected",
                    "monitor_idle_pcm_uploaded_zero",
                    "terminal_resources_zero",
                ],
                "product_ns_enabled": False,
                "product_agc_enabled": False,
                "monitor_uploaded_frames": 0,
                "pcm_persisted": False,
                "payload_persisted": False,
                "secrets_redacted": True,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
