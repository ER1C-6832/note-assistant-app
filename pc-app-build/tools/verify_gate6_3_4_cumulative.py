"""Run cumulative automated acceptance through combined Gate 6.3+6.4."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAIL_LINES = 24
_SECRET = re.compile(r"(?i)((?:token|password|api[_-]?key|secret)[:=]\s*)[^\s,;]+")


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    command: tuple[str, ...]


def _run(check: Check, *, pytest_temp_root: str) -> dict[str, object]:
    started = time.perf_counter_ns()
    private_basetemp = str(Path(pytest_temp_root) / "basetemp")
    addopts = " ".join(
        value
        for value in (
            os.environ.get("PYTEST_ADDOPTS", "").strip(),
            f"--basetemp={private_basetemp}",
        )
        if value
    )
    completed = subprocess.run(
        check.command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={
            **os.environ,
            "PYTHONUTF8": "1",
            "QT_QPA_PLATFORM": "offscreen",
            "PYTEST_DEBUG_TEMPROOT": pytest_temp_root,
            "PYTEST_ADDOPTS": addopts,
        },
        check=False,
    )

    def redact(value: str) -> list[str]:
        return _SECRET.sub(r"\1<redacted>", value).splitlines()[-TAIL_LINES:]

    return {
        "name": check.name,
        "command": list(check.command),
        "returncode": completed.returncode,
        "duration_ms": round((time.perf_counter_ns() - started) / 1_000_000, 3),
        "status": "passed" if completed.returncode == 0 else "failed",
        "stdout_tail": redact(completed.stdout or ""),
        "stderr_tail": redact(completed.stderr or ""),
    }


def main() -> int:
    python = sys.executable
    checks = (
        Check("compileall", (python, "-m", "compileall", "-q", "apps", "tools", "tests")),
        Check("black", (python, "-m", "black", "--check", "apps", "tools", "tests")),
        Check("ruff", (python, "-m", "ruff", "check", "apps", "tools", "tests")),
        Check("pytest_all", (python, "-m", "pytest", "-W", "error", "tests", "-q")),
        Check("qml_smoke", (python, "tools/verify_gate2_6_ui_smoke.py")),
        Check("gate6_2_cumulative", (python, "tools/verify_gate6_2_cumulative.py")),
        Check("gate6_3_4_fake_barge_in", (python, "tools/verify_gate6_3_4_fake_barge_in.py")),
    )
    results: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(
        prefix="note-assistant-gate6-3-4-pytest-",
        ignore_cleanup_errors=True,
    ) as pytest_temp_root:
        for check in checks:
            print(f"[Gate 6.3+6.4] {check.name}", file=sys.stderr, flush=True)
            result = _run(check, pytest_temp_root=pytest_temp_root)
            results.append(result)
            if result["status"] != "passed":
                break
    passed = len(results) == len(checks) and all(item["status"] == "passed" for item in results)
    print(
        json.dumps(
            {
                "status": "gate6_3_4_cumulative_complete" if passed else "failed",
                "baseline_expectation": "single-process Gate 1.1 through Gate 6.4",
                "checks": results,
                "windows_product_aec": "enabled_for_playback_monitor",
                "windows_product_ns": "deferred_after_double_talk_evidence",
                "windows_product_agc": "disabled",
                "acoustic_barge_in_default_enabled": False,
                "monitor_uploaded_frames": 0,
                "macos_status": "deferred",
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
