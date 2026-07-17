"""Verify Gate 6.0 framework-neutral probe contracts without real devices."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.assistant.audio.gate6_probe import (  # noqa: E402
    PROBE_CAPTURE_QUEUE_CAPACITY,
    PROBE_INTERNAL_BLOCK_MS,
    PROBE_RENDER_QUEUE_CAPACITY,
    PROBE_WATCHDOG_MS,
    ProbeStatus,
    run_fake_probe_contract,
)


def main() -> int:
    report = run_fake_probe_contract()
    value = report.public_dict()
    result = value["result"]
    terminal = value["terminal"]
    verified = all(
        (
            value["status"] == ProbeStatus.COMPLETE.value,
            result["device_counts"] == {"empty": 0, "one": 1, "directional": 2, "many": 3},
            result["overflow_seen"] is True,
            result["kws_cooldown_rejected"] is True,
            result["product_audio_topology_changed"] is False,
            result["pcm_persisted"] is False,
            result["terminal_zero"] is True,
            terminal["capture_stream"] == 0,
            terminal["output_stream"] == 0,
            terminal["duplex_session"] == 0,
            terminal["processing_worker"] == 0,
            terminal["kws_worker"] == 0,
            terminal["microphone_lease"] == "none",
            terminal["pending_tasks"] == [],
        )
    )
    value.update(
        {
            "status": "gate6_0_fake_probe_complete" if verified else "failed",
            "budgets": {
                "render_queue_capacity": PROBE_RENDER_QUEUE_CAPACITY,
                "capture_queue_capacity": PROBE_CAPTURE_QUEUE_CAPACITY,
                "internal_block_ms": PROBE_INTERNAL_BLOCK_MS,
                "watchdog_ms": PROBE_WATCHDOG_MS,
            },
            "real_windows_evidence": "not_run",
            "real_macos_evidence": "pending_real_macos",
        }
    )
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
