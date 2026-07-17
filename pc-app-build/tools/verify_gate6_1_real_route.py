"""Inspect the real Windows Gate 6.1 route and optionally test the microphone."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.assistant.audio.session_supervisor import AudioSessionSupervisor  # noqa: E402
from app.assistant.preferences import AssistantPreferencesStore  # noqa: E402


async def _run(include_microphone_test: bool, duration: float) -> tuple[dict[str, object], bool]:
    with tempfile.TemporaryDirectory(prefix="note-assistant-gate6-1-real-") as directory:
        supervisor = AudioSessionSupervisor(
            AssistantPreferencesStore(Path(directory) / "preferences.json")
        )
        try:
            await supervisor.start()
            microphone_test = (
                await supervisor.microphone_test(duration_seconds=duration)
                if include_microphone_test
                else {"status": "not_run"}
            )
            before_close = supervisor.diagnostics()
            input_items = supervisor.input_device_items()
            output_items = supervisor.output_device_items()
        finally:
            await supervisor.close()
        terminal = supervisor.diagnostics()
        passed = all(
            (
                before_close["route_state"] == "ready",
                len(input_items) >= 2,
                len(output_items) >= 2,
                terminal["capture_activity"] == "inactive",
                terminal["playback_activity"] == "inactive",
                terminal["microphone_lease"]["owner"] == "none",
                terminal["route_observer_running"] is False,
                terminal["duplex_open_stream_count"] == 0,
                terminal["pending_route_tasks"] == [],
            )
        )
        return (
            {
                "status": "gate6_1_real_route_complete" if passed else "failed",
                "platform": sys.platform,
                "route": before_close,
                "input_devices": input_items,
                "output_devices": output_items,
                "microphone_test": microphone_test,
                "terminal": terminal,
                "private_device_ids_exposed": False,
                "pcm_persisted": False,
                "product_uplink_frames": 0,
                "secrets_redacted": True,
            },
            passed,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--microphone-test", action="store_true")
    parser.add_argument("--duration", type=float, default=1.0)
    args = parser.parse_args()
    report, passed = asyncio.run(_run(args.microphone_test, args.duration))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
