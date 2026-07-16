"""Run the canonical non-interactive Gate 4 cumulative verifier."""

from __future__ import annotations

import argparse
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

_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization:\s*bearer\s+)[^\s]+"),
    re.compile(r"(?i)(token[=:]\s*)[^\s,;]+"),
    re.compile(r"(?i)(password[=:]\s*)[^\s,;]+"),
    re.compile(r"(?i)(api[_-]?key[=:]\s*)[^\s,;]+"),
)


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    command: tuple[str, ...]


def _redact(text: str) -> str:
    clean = text
    for pattern in _SECRET_PATTERNS:
        clean = pattern.sub(r"\1<redacted>", clean)
    clean = re.sub(r"([?&](?:token|key|secret|auth)=)[^&\s]+", r"\1<redacted>", clean)
    return clean


def _tail(text: str) -> list[str]:
    lines = _redact(text).splitlines()
    return lines[-TAIL_LINES:]


def _environment_blocked(returncode: int, stdout: str, stderr: str) -> bool:
    if returncode == 2:
        return True
    combined = f"{stdout}\n{stderr}".lower()
    return any(
        marker in combined
        for marker in (
            "no module named black",
            "no module named ruff",
            "no module named pytest",
            "is not recognized as an internal or external command",
            "permission denied",
        )
    )


def _run_check(check: Check) -> dict[str, object]:
    started = time.perf_counter_ns()
    completed = subprocess.run(
        check.command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONUTF8": "1"},
        check=False,
    )
    duration_ms = round((time.perf_counter_ns() - started) / 1_000_000, 3)
    blocked = _environment_blocked(
        completed.returncode,
        completed.stdout,
        completed.stderr,
    )
    return {
        "name": check.name,
        "command": list(check.command),
        "returncode": completed.returncode,
        "duration_ms": duration_ms,
        "status": ("passed" if completed.returncode == 0 else ("blocked" if blocked else "failed")),
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
    }


def _checks(*, include_real_stop: bool) -> list[Check]:
    python = sys.executable
    checks = [
        Check(
            "compileall",
            (python, "-m", "compileall", "-q", "apps", "tools", "tests"),
        ),
        Check(
            "black",
            (python, "-m", "black", "--check", "apps", "tools", "tests"),
        ),
        Check(
            "ruff",
            (python, "-m", "ruff", "check", "apps", "tools", "tests"),
        ),
        Check(
            "pytest_all",
            (python, "-m", "pytest", "-W", "error", "tests", "-q"),
        ),
        Check(
            "gate4_fake_playback",
            (python, "tools/verify_gate4_2_fake_playback.py"),
        ),
        Check(
            "gate4_fake_two_turn",
            (python, "tools/verify_gate4_3_fake_two_turn.py"),
        ),
    ]
    if include_real_stop:
        checks.append(
            Check(
                "gate4_real_stop_during_playback",
                (python, "tools/verify_gate4_4_real_stop_during_playback.py"),
            )
        )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--include-real-stop",
        action="store_true",
        help="also run the interactive Windows stop-during-playback acceptance",
    )
    args = parser.parse_args()

    results: list[dict[str, object]] = []
    for check in _checks(include_real_stop=args.include_real_stop):
        print(f"[Gate 4] {check.name}", file=sys.stderr, flush=True)
        result = _run_check(check)
        results.append(result)
        if result["status"] != "passed":
            break

    blocked = any(result["status"] == "blocked" for result in results)
    failed = any(result["status"] == "failed" for result in results)
    passed = (
        not blocked
        and not failed
        and len(results) == len(_checks(include_real_stop=args.include_real_stop))
    )
    payload = {
        "status": (
            "gate4_cumulative_complete"
            if passed
            else ("gate4_cumulative_blocked" if blocked else "failed")
        ),
        "baseline_expectation": "single-process Gate 1.1 through Gate 4.4",
        "include_real_stop": args.include_real_stop,
        "checks": results,
        "payload_persisted": False,
        "secrets_redacted": True,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    if passed:
        return 0
    return 2 if blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
