from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PC_BUILD_ROOT = Path(__file__).resolve().parents[2]
SMOKE_SCRIPT = Path(__file__).with_name("startup_smoke.py")


def test_offscreen_application_starts_and_exits_in_one_process() -> None:
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["QT_QUICK_CONTROLS_STYLE"] = "Basic"

    result = subprocess.run(
        [sys.executable, str(SMOKE_SCRIPT)],
        cwd=PC_BUILD_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    output = f"{result.stdout}\n{result.stderr}"

    assert result.returncode == 0, output
    assert "GATE1_7_STARTUP_OK" in output
    assert "Traceback (most recent call last)" not in output
    assert "TypeError:" not in output
    assert "ReferenceError:" not in output
    assert "QML failed to load" not in output
