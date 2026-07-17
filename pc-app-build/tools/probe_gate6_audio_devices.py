"""Enumerate public audio device capabilities without exposing endpoint IDs."""

from __future__ import annotations

import argparse

from _gate6_probe_cli import emit_report, emit_unexpected
from app.assistant.audio.gate6_probe import ProbeScenario, ProbeStatus
from app.assistant.audio.gate6_pyaudio_probe import (
    Gate60PyAudioUnavailable,
    enumerate_pyaudio_devices,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        result = enumerate_pyaudio_devices()
    except Gate60PyAudioUnavailable as exc:
        return emit_report(
            scenario=ProbeScenario.DEVICE_INVENTORY,
            status=ProbeStatus.BLOCKED,
            result={"message": str(exc)},
            error_code="pyaudio_unavailable",
        )
    except Exception as exc:
        return emit_unexpected(ProbeScenario.DEVICE_INVENTORY, exc)
    usable = result["input_count"] > 0 and result["output_count"] > 0
    return emit_report(
        scenario=ProbeScenario.DEVICE_INVENTORY,
        status=ProbeStatus.COMPLETE if usable else ProbeStatus.BLOCKED,
        result=result,
        terminal={
            "capture_stream": 0,
            "output_stream": 0,
            "duplex_session": 0,
            "processing_worker": 0,
            "kws_worker": 0,
            "microphone_lease": "none",
            "pending_tasks": [],
            "second_python_process": 0,
        },
        error_code=None if usable else "no_usable_duplex_route",
    )


if __name__ == "__main__":
    raise SystemExit(main())
