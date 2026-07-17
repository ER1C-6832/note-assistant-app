"""Run the cumulative automated/Fake acceptance through Gate 6.1."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
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


def _run(check: Check) -> dict[str, object]:
    started = time.perf_counter_ns()
    completed = subprocess.run(
        check.command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONUTF8": "1", "QT_QPA_PLATFORM": "offscreen"},
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
        Check("gate6_0_cumulative", (python, "tools/verify_gate6_0_cumulative.py")),
        Check("gate6_1_fake_session", (python, "tools/verify_gate6_1_fake_session.py")),
    )
    results: list[dict[str, object]] = []
    for check in checks:
        print(f"[Gate 6.1] {check.name}", file=sys.stderr, flush=True)
        result = _run(check)
        results.append(result)
        if result["status"] != "passed":
            break
    passed = len(results) == len(checks) and all(item["status"] == "passed" for item in results)
    print(
        json.dumps(
            {
                "status": "gate6_1_cumulative_complete" if passed else "failed",
                "baseline_expectation": "single-process Gate 1.1 through Gate 6.1",
                "checks": results,
                "windows_product_audio_session": "implemented",
                "macos_status": "deferred_after_windows_gate6",
                "product_aec_enabled": False,
                "product_kws_enabled": False,
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
