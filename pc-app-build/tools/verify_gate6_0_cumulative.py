"""Run Gate 1 through Gate 6.0 automated/Fake checks and optional real probes."""

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
    re.compile(r"(?i)((?:token|password|api[_-]?key|secret)[:=]\s*)[^\s,;]+"),
)


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    command: tuple[str, ...]
    interactive: bool = False


def _redact(text: str) -> str:
    value = text
    for pattern in _SECRET_PATTERNS:
        value = pattern.sub(r"\1<redacted>", value)
    return value


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
            "pyaudio is not installed",
            "sherpa_onnx_not_installed",
            "aec_audio_processing_not_installed",
            "is not recognized as an internal or external command",
            "permission denied",
        )
    )


def _run_check(check: Check) -> dict[str, object]:
    started = time.perf_counter_ns()
    completed = subprocess.run(
        check.command,
        cwd=ROOT,
        capture_output=not check.interactive,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONUTF8": "1"},
        check=False,
    )
    duration_ms = round((time.perf_counter_ns() - started) / 1_000_000, 3)
    blocked = _environment_blocked(
        completed.returncode,
        completed.stdout or "",
        completed.stderr or "",
    )
    return {
        "name": check.name,
        "command": list(check.command),
        "returncode": completed.returncode,
        "duration_ms": duration_ms,
        "status": ("passed" if completed.returncode == 0 else ("blocked" if blocked else "failed")),
        "stdout_tail": _tail(completed.stdout or ""),
        "stderr_tail": _tail(completed.stderr or ""),
    }


def _checks(args: argparse.Namespace) -> list[Check]:
    python = sys.executable
    checks = [
        Check("compileall", (python, "-m", "compileall", "-q", "apps", "tools", "tests")),
        Check("black", (python, "-m", "black", "--check", "apps", "tools", "tests")),
        Check("ruff", (python, "-m", "ruff", "check", "apps", "tools", "tests")),
        Check("pytest_all", (python, "-m", "pytest", "-W", "error", "tests", "-q")),
        Check("qml_smoke", (python, "tools/verify_gate2_6_ui_smoke.py")),
        Check("gate5_cumulative", (python, "tools/verify_gate5_4_cumulative.py")),
        Check("gate6_0_fake_probe", (python, "tools/verify_gate6_0_fake_probe.py")),
    ]
    if args.include_real_devices:
        checks.append(Check("gate6_0_devices", (python, "tools/probe_gate6_audio_devices.py")))
    if args.include_real_duplex:
        checks.append(
            Check(
                "gate6_0_duplex",
                (
                    python,
                    "tools/probe_gate6_duplex.py",
                    "--duration",
                    str(args.duration),
                ),
                interactive=True,
            )
        )
    if args.include_real_aec:
        checks.extend(
            (
                Check("gate6_0_aec_capability", (python, "tools/probe_gate6_aec.py")),
                Check(
                    "gate6_0_aec_far_end_only",
                    (
                        python,
                        "tools/probe_gate6_aec.py",
                        "--scenario",
                        "far_end_only",
                        "--duration",
                        str(max(3.0, args.duration)),
                        "--stream-delay-ms",
                        args.aec_stream_delay_ms,
                        "--processing-mode",
                        args.aec_processing_mode,
                    ),
                    interactive=True,
                ),
                Check(
                    "gate6_0_aec_double_talk",
                    (
                        python,
                        "tools/probe_gate6_aec.py",
                        "--scenario",
                        "double_talk",
                        "--duration",
                        str(max(4.0, args.duration)),
                        "--stream-delay-ms",
                        args.aec_stream_delay_ms,
                        "--processing-mode",
                        args.aec_processing_mode,
                        "--speech-start-delay",
                        str(args.aec_speech_start_delay),
                    ),
                    interactive=True,
                ),
            )
        )
    if args.include_real_kws:
        checks.append(
            Check(
                "gate6_0_kws_live",
                (
                    python,
                    "tools/probe_gate6_kws.py",
                    "--tokens",
                    str(args.kws_tokens),
                    "--encoder",
                    str(args.kws_encoder),
                    "--decoder",
                    str(args.kws_decoder),
                    "--joiner",
                    str(args.kws_joiner),
                    "--keywords-file",
                    str(args.kws_keywords_file),
                    "--duration",
                    str(args.kws_duration),
                ),
                interactive=True,
            )
        )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-real-devices", action="store_true")
    parser.add_argument("--include-real-duplex", action="store_true")
    parser.add_argument("--include-real-aec", action="store_true")
    parser.add_argument("--include-real-kws", action="store_true")
    parser.add_argument("--duration", type=float, default=3.0)
    parser.add_argument("--aec-stream-delay-ms", default="auto")
    parser.add_argument(
        "--aec-processing-mode",
        choices=("aec_only", "aec_ns", "ns_only"),
        default="aec_ns",
    )
    parser.add_argument("--aec-speech-start-delay", type=float, default=1.5)
    parser.add_argument("--kws-duration", type=float, default=12.0)
    parser.add_argument("--kws-tokens", type=Path)
    parser.add_argument("--kws-encoder", type=Path)
    parser.add_argument("--kws-decoder", type=Path)
    parser.add_argument("--kws-joiner", type=Path)
    parser.add_argument("--kws-keywords-file", type=Path)
    args = parser.parse_args()
    if args.include_real_kws and not all(
        (
            args.kws_tokens,
            args.kws_encoder,
            args.kws_decoder,
            args.kws_joiner,
            args.kws_keywords_file,
        )
    ):
        parser.error("--include-real-kws requires all five --kws-* model paths")
    expected = _checks(args)
    results: list[dict[str, object]] = []
    for check in expected:
        print(f"[Gate 6.0] {check.name}", file=sys.stderr, flush=True)
        result = _run_check(check)
        results.append(result)
        if result["status"] != "passed":
            break
    blocked = any(item["status"] == "blocked" for item in results)
    failed = any(item["status"] == "failed" for item in results)
    passed = not blocked and not failed and len(results) == len(expected)
    status = (
        "gate6_0_cumulative_complete"
        if passed
        else ("gate6_0_cumulative_blocked" if blocked else "failed")
    )
    print(
        json.dumps(
            {
                "status": status,
                "baseline_expectation": "single-process Gate 1.1 through Gate 6.0",
                "include_real_devices": args.include_real_devices,
                "include_real_duplex": args.include_real_duplex,
                "include_real_aec": args.include_real_aec,
                "include_real_kws": args.include_real_kws,
                "checks": results,
                "windows_backend_decision": "pending_real_probe_report",
                "macos_status": "pending_real_macos",
                "product_audio_topology_changed": False,
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
