"""Run the canonical non-interactive Gate 1 through Gate 5.3 verifier."""

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
    re.compile(r"(?i)(token[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(password[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(api[_-]?key[:=]\s*)[^\s,;]+"),
)


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    command: tuple[str, ...]


def _redact(text: str) -> str:
    clean = text
    for pattern in _SECRET_PATTERNS:
        clean = pattern.sub(r"\1<redacted>", clean)
    return re.sub(
        r"([?&](?:token|key|secret|auth)=)[^&\s]+",
        r"\1<redacted>",
        clean,
    )


def _tail(text: str) -> list[str]:
    return _redact(text).splitlines()[-TAIL_LINES:]


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


def _checks(
    *,
    include_gate4_real: bool,
    include_gate5_real: bool,
    include_gate5_real_ui_language: bool,
) -> list[Check]:
    python = sys.executable
    checks = [
        Check("compileall", (python, "-m", "compileall", "-q", "apps", "tools", "tests")),
        Check("black", (python, "-m", "black", "--check", "apps", "tools", "tests")),
        Check("ruff", (python, "-m", "ruff", "check", "apps", "tools", "tests")),
        Check("pytest_all", (python, "-m", "pytest", "-W", "error", "tests", "-q")),
        Check("gate4_fake_playback", (python, "tools/verify_gate4_2_fake_playback.py")),
        Check("gate4_fake_two_turn", (python, "tools/verify_gate4_3_fake_two_turn.py")),
        Check("gate5_0_protocol", (python, "tools/verify_gate5_0_protocol.py")),
        Check("gate5_1_read_ui", (python, "tools/verify_gate5_1_read_ui.py")),
        Check("gate5_2_mutations", (python, "tools/verify_gate5_2_mutations.py")),
        Check(
            "gate5_3_confirmation",
            (python, "tools/verify_gate5_3_confirmation.py"),
        ),
    ]
    if include_gate4_real:
        checks.append(
            Check(
                "gate4_real_stop_during_playback",
                (python, "tools/verify_gate4_4_real_stop_during_playback.py"),
            )
        )
    if include_gate5_real:
        checks.append(
            Check(
                "gate5_0_real_protocol",
                (python, "tools/verify_gate5_0_real_protocol.py"),
            )
        )
        if include_gate5_real_ui_language:
            checks.append(
                Check(
                    "gate5_1_real_ui_language",
                    (python, "tools/verify_gate5_1_real_ui_language.py"),
                )
            )
        else:
            checks.append(
                Check(
                    "gate5_1_real_read_ui",
                    (python, "tools/verify_gate5_1_real_read_ui.py"),
                )
            )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-gate4-real", action="store_true")
    parser.add_argument("--include-gate5-real", action="store_true")
    parser.add_argument(
        "--include-gate5-real-ui-language",
        action="store_true",
        help=(
            "launch the actual desktop UI and require interactive natural-language "
            "tool calls; implies --include-gate5-real"
        ),
    )
    args = parser.parse_args()
    include_gate5_real = bool(args.include_gate5_real or args.include_gate5_real_ui_language)
    expected = _checks(
        include_gate4_real=args.include_gate4_real,
        include_gate5_real=include_gate5_real,
        include_gate5_real_ui_language=args.include_gate5_real_ui_language,
    )
    results: list[dict[str, object]] = []
    for check in expected:
        print(f"[Gate 5.3] {check.name}", file=sys.stderr, flush=True)
        result = _run_check(check)
        results.append(result)
        if result["status"] != "passed":
            break

    blocked = any(result["status"] == "blocked" for result in results)
    failed = any(result["status"] == "failed" for result in results)
    passed = not blocked and not failed and len(results) == len(expected)
    print(
        json.dumps(
            {
                "status": (
                    "gate5_3_cumulative_complete"
                    if passed
                    else ("gate5_3_cumulative_blocked" if blocked else "failed")
                ),
                "baseline_expectation": "single-process Gate 1.1 through Gate 5.3",
                "include_gate4_real": args.include_gate4_real,
                "include_gate5_real": include_gate5_real,
                "include_gate5_real_ui_language": (args.include_gate5_real_ui_language),
                "checks": results,
                "payload_persisted": False,
                "secrets_redacted": True,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    if passed:
        return 0
    return 2 if blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
