"""Run a bounded real capture/render timing probe; no PCM is persisted."""

from __future__ import annotations

import argparse

from _gate6_probe_cli import emit_report, emit_unexpected
from app.assistant.audio.gate6_probe import ProbeScenario, ProbeStatus
from app.assistant.audio.gate6_pyaudio_probe import (
    Gate60PyAudioUnavailable,
    run_pyaudio_duplex_probe,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=2.0)
    parser.add_argument("--input-device-index", type=int)
    parser.add_argument("--output-device-index", type=int)
    parser.add_argument("--sample-rate", type=int, default=16_000)
    parser.add_argument("--channels", type=int, default=1)
    parser.add_argument("--frame-ms", type=int, choices=(10, 20), default=20)
    args = parser.parse_args()
    try:
        result = run_pyaudio_duplex_probe(
            duration_seconds=args.duration,
            input_device_index=args.input_device_index,
            output_device_index=args.output_device_index,
            sample_rate_hz=args.sample_rate,
            channels=args.channels,
            frame_duration_ms=args.frame_ms,
        )
    except Gate60PyAudioUnavailable as exc:
        return emit_report(
            scenario=ProbeScenario.DUPLEX,
            status=ProbeStatus.BLOCKED,
            result={"message": str(exc)},
            error_code="pyaudio_unavailable",
        )
    except Exception as exc:
        return emit_unexpected(ProbeScenario.DUPLEX, exc)
    passed = result.get("status") == "probe_complete" and not result.get("errors")
    return emit_report(
        scenario=ProbeScenario.DUPLEX,
        status=ProbeStatus.COMPLETE if passed else ProbeStatus.FAILED,
        result=result,
        terminal=result.get("terminal", {}),
        error_code=None if passed else "duplex_probe_failed",
    )


if __name__ == "__main__":
    raise SystemExit(main())
