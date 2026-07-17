"""Shared CLI helpers for Gate 6.0 probe entrypoints."""

from __future__ import annotations

import json
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.assistant.audio.gate6_probe import (  # noqa: E402
    ProbeReport,
    ProbeScenario,
    ProbeStatus,
    dumps_probe_report,
    ensure_probe_report_safe,
    platform_name,
    sanitize_public_value,
)


def emit_report(
    *,
    scenario: ProbeScenario,
    status: ProbeStatus,
    result: dict[str, object],
    terminal: dict[str, object] | None = None,
    error_code: str | None = None,
    human_observation: str = "not_run",
) -> int:
    report = ProbeReport(
        scenario=scenario,
        status=status,
        platform_public=platform_name(),
        result=result,
        terminal=terminal or result.get("terminal", {}),
        error_code=error_code,
        human_observation=human_observation,
    )
    print(dumps_probe_report(report))
    if status is ProbeStatus.COMPLETE:
        return 0
    if status in {ProbeStatus.BLOCKED, ProbeStatus.PENDING_REAL}:
        return 2
    return 1


def emit_unexpected(scenario: ProbeScenario, exc: Exception) -> int:
    return emit_report(
        scenario=scenario,
        status=ProbeStatus.FAILED,
        result={
            "exception_type": type(exc).__name__,
            "message": "probe failed at a bounded native boundary",
            "payload_persisted": False,
        },
        terminal={},
        error_code="probe_unexpected_failure",
    )


def emit_raw(value: dict[str, object]) -> None:
    safe = sanitize_public_value(value)
    if not isinstance(safe, dict):
        raise TypeError("safe probe output must be an object")
    ensure_probe_report_safe(safe)
    print(json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True))


def require_windows_or_macos(*, allow_other: bool = False) -> None:
    if allow_other:
        return
    system = platform.system().lower()
    if system not in {"windows", "darwin"}:
        raise RuntimeError("real Gate 6.0 audio probes require Windows or macOS")
