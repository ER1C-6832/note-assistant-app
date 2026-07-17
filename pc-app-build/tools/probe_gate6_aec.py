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


def _stream_delay(value: str) -> int | None:
    if value.casefold() == "auto":
        return None
    try:
        delay_ms = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use auto or an integer from 0 to 500") from exc
    if not 0 <= delay_ms <= 500:
        raise argparse.ArgumentTypeError("stream delay must be from 0 to 500 ms")
    return delay_ms


def _prompt(scenario: str, speech_start_delay: float) -> None:
    if scenario == "far_end_only":
        print(
            "[Gate 6.0] Far-end-only: 测试音播放期间请保持安静。不会保存音频。",
            file=sys.stderr,
            flush=True,
        )
    else:
        print(
            "[Gate 6.0] Double-talk: 测试开始后先保持安静 "
            f"{speech_start_delay:g} 秒，然后持续重复说：小智音频双讲测试。不会保存音频。",
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
    parser.add_argument(
        "--stream-delay-ms",
        type=_stream_delay,
        default=None,
        metavar="auto|0..500",
        help="APM render/capture delay; default auto uses opened stream latencies",
    )
    parser.add_argument(
        "--processing-mode",
        choices=("aec_only", "aec_ns", "ns_only"),
        default="aec_ns",
    )
    parser.add_argument("--speech-start-delay", type=float, default=1.5)
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
    _prompt(args.scenario, args.speech_start_delay)
    try:
        result = run_live_aec_probe(
            scenario=args.scenario,
            duration_seconds=args.duration,
            input_device_index=args.input_device_index,
            output_device_index=args.output_device_index,
            stream_delay_ms=args.stream_delay_ms,
            processing_mode=args.processing_mode,
            speech_start_delay_seconds=args.speech_start_delay,
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
    acceptance = result.get("acceptance", {})
    passed = (
        result.get("status") == "probe_complete"
        and isinstance(acceptance, dict)
        and acceptance.get("accepted") is True
        and not result.get("errors")
    )
    failure_code = (
        None
        if passed
        else (
            acceptance.get("failure_code", "aec_live_probe_failed")
            if isinstance(acceptance, dict)
            else "aec_live_probe_failed"
        )
    )
    return emit_report(
        scenario=(
            ProbeScenario.AEC_FAR_END_ONLY
            if args.scenario == "far_end_only"
            else ProbeScenario.AEC_DOUBLE_TALK
        ),
        status=ProbeStatus.COMPLETE if passed else ProbeStatus.FAILED,
        result={"capabilities": capabilities, **result},
        terminal=result.get("terminal", {}),
        error_code=failure_code,
        human_observation="required_and_machine_checked",
    )


if __name__ == "__main__":
    raise SystemExit(main())
