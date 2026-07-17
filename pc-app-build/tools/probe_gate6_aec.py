"""Probe AEC backend capability and optional real far-end/double-talk behavior."""

from __future__ import annotations

import argparse
import sys

from _gate6_probe_cli import emit_report, emit_unexpected
from app.assistant.audio.gate6_backend_probe import (
    Gate60BackendUnavailable,
    run_live_aec_probe,
)
from app.assistant.audio.gate6_probe import (
    ProbeScenario,
    ProbeStatus,
    detect_backend_capabilities,
)


def _prompt(scenario: str) -> None:
    if scenario == "far_end_only":
        print(
            "[Gate 6.0] Far-end-only: 测试音播放期间请保持安静。不会保存音频。",
            file=sys.stderr,
            flush=True,
        )
    else:
        print(
            "[Gate 6.0] Double-talk: 测试音播放期间请重复说：小智音频双讲测试。不会保存音频。",
            file=sys.stderr,
            flush=True,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        choices=("capability", "far_end_only", "double_talk"),
        default="capability",
    )
    parser.add_argument("--duration", type=float, default=4.0)
    parser.add_argument("--input-device-index", type=int)
    parser.add_argument("--output-device-index", type=int)
    args = parser.parse_args()
    capabilities = [item.public_dict() for item in detect_backend_capabilities()]
    if args.scenario == "capability":
        return emit_report(
            scenario=ProbeScenario.AEC_CAPABILITY,
            status=ProbeStatus.COMPLETE,
            result={
                "capabilities": capabilities,
                "backend_selected": None,
                "selection_pending_real_evidence": True,
                "agc_product_default": False,
                "pcm_persisted": False,
            },
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
        )
    _prompt(args.scenario)
    try:
        result = run_live_aec_probe(
            scenario=args.scenario,
            duration_seconds=args.duration,
            input_device_index=args.input_device_index,
            output_device_index=args.output_device_index,
        )
    except Gate60BackendUnavailable as exc:
        return emit_report(
            scenario=(
                ProbeScenario.AEC_FAR_END_ONLY
                if args.scenario == "far_end_only"
                else ProbeScenario.AEC_DOUBLE_TALK
            ),
            status=ProbeStatus.BLOCKED,
            result={
                "capabilities": capabilities,
                "message": str(exc),
                "install_hint": "pip install aec-audio-processing==1.0.1",
            },
            error_code=exc.code,
        )
    except Exception as exc:
        return emit_unexpected(
            (
                ProbeScenario.AEC_FAR_END_ONLY
                if args.scenario == "far_end_only"
                else ProbeScenario.AEC_DOUBLE_TALK
            ),
            exc,
        )
    passed = result.get("status") == "probe_complete" and not result.get("errors")
    return emit_report(
        scenario=(
            ProbeScenario.AEC_FAR_END_ONLY
            if args.scenario == "far_end_only"
            else ProbeScenario.AEC_DOUBLE_TALK
        ),
        status=ProbeStatus.COMPLETE if passed else ProbeStatus.FAILED,
        result={"capabilities": capabilities, **result},
        terminal=result.get("terminal", {}),
        error_code=None if passed else "aec_live_probe_failed",
        human_observation="required",
    )


if __name__ == "__main__":
    raise SystemExit(main())
