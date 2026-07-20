"""Run cumulative automated/Fake acceptance through Gate 6.2."""

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
    inherited_addopts = os.environ.get("PYTEST_ADDOPTS", "").strip()
    pytest_addopts = " ".join(
        value for value in (inherited_addopts, f"--basetemp={private_basetemp}") if value
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
            "PYTEST_ADDOPTS": pytest_addopts,
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
        Check("gate6_1_fake_session", (python, "tools/verify_gate6_1_fake_session.py")),
        Check("gate6_2_fake_kws", (python, "tools/verify_gate6_2_fake_kws.py")),
        Check(
            "gate6_2_model_layout",
            (python, "tools/verify_gate6_2_model_package.py", "--allow-missing"),
        ),
    )
    results: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(
        prefix="note-assistant-gate6-2-pytest-",
        ignore_cleanup_errors=True,
    ) as pytest_temp_root:
        for check in checks:
            print(f"[Gate 6.2] {check.name}", file=sys.stderr, flush=True)
            result = _run(check, pytest_temp_root=pytest_temp_root)
            results.append(result)
            if result["status"] != "passed":
                break
    passed = len(results) == len(checks) and all(item["status"] == "passed" for item in results)
    print(
        json.dumps(
            {
                "status": "gate6_2_cumulative_complete" if passed else "failed",
                "baseline_expectation": "single-process Gate 1.1 through Gate 6.2",
                "checks": results,
                "offline_kws_default_enabled": False,
                "idle_microphone_uploaded_frames": 0,
                "product_aec_enabled": False,
                "macos_status": "deferred_after_windows_gate6",
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
