"""Probe sherpa-onnx KWS import/model/live microphone/cooldown behavior."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from _gate6_probe_cli import emit_report, emit_unexpected
from app.assistant.audio.gate6_backend_probe import (
    Gate60BackendUnavailable,
    SherpaKwsModelPaths,
    run_live_sherpa_kws_probe,
)
from app.assistant.audio.gate6_probe import (
    ProbeScenario,
    ProbeStatus,
    process_runtime_sample,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokens", type=Path)
    parser.add_argument("--encoder", type=Path)
    parser.add_argument("--decoder", type=Path)
    parser.add_argument("--joiner", type=Path)
    parser.add_argument("--keywords-file", type=Path)
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--input-device-index", type=int)
    parser.add_argument("--cooldown-ms", type=int, default=1500)
    args = parser.parse_args()
    module_available = importlib.util.find_spec("sherpa_onnx") is not None
    supplied = [
        args.tokens,
        args.encoder,
        args.decoder,
        args.joiner,
        args.keywords_file,
    ]
    if not any(supplied):
        return emit_report(
            scenario=ProbeScenario.KWS_IMPORT,
            status=ProbeStatus.COMPLETE if module_available else ProbeStatus.BLOCKED,
            result={
                "engine": "sherpa-onnx KeywordSpotter",
                "module_available": module_available,
                "model_supplied": False,
                "model_downloaded_at_runtime": False,
                "runtime_sample": process_runtime_sample(),
                "next_step": (
                    "rerun with five explicit local model paths"
                    if module_available
                    else "install sherpa-onnx, then provide local model paths"
                ),
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
            error_code=None if module_available else "sherpa_onnx_not_installed",
        )
    if not all(supplied):
        parser.error("all five KWS model paths must be supplied together")
    print(
        "[Gate 6.0] 请在 10 秒窗口内说两次唤醒词；不会保存或上传麦克风音频。",
        file=sys.stderr,
        flush=True,
    )
    model = SherpaKwsModelPaths(
        args.tokens,
        args.encoder,
        args.decoder,
        args.joiner,
        args.keywords_file,
    )
    try:
        result = run_live_sherpa_kws_probe(
            model=model,
            duration_seconds=args.duration,
            input_device_index=args.input_device_index,
            cooldown_ms=args.cooldown_ms,
        )
    except Gate60BackendUnavailable as exc:
        return emit_report(
            scenario=ProbeScenario.KWS_LIVE,
            status=ProbeStatus.BLOCKED,
            result={"message": str(exc), "model_downloaded_at_runtime": False},
            error_code=exc.code,
        )
    except Exception as exc:
        return emit_unexpected(ProbeScenario.KWS_LIVE, exc)
    passed = result.get("status") == "probe_complete" and not result.get("errors")
    return emit_report(
        scenario=ProbeScenario.KWS_LIVE,
        status=ProbeStatus.COMPLETE if passed else ProbeStatus.FAILED,
        result=result,
        terminal=result.get("terminal", {}),
        error_code=None if passed else "kws_live_probe_failed",
        human_observation="required",
    )


if __name__ == "__main__":
    raise SystemExit(main())
