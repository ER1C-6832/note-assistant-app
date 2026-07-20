"""Run one real Windows product-path acoustic barge-in acceptance."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.app_paths import AppPaths  # noqa: E402
from app.assistant import (  # noqa: E402
    AssistantActivationStatus,
    AssistantAudioStatus,
    VoiceInteractionMode,
    redact_error_text,
)
from app.bootstrap import create_assistant_runtime  # noqa: E402

ACTIVATION_TIMEOUT_SECONDS = 25.0
CONNECT_TIMEOUT_SECONDS = 20.0
CAPTURE_TIMEOUT_SECONDS = 12.0
PLAYBACK_TIMEOUT_SECONDS = 90.0
BARGE_IN_TIMEOUT_SECONDS = 45.0
RESPONSE_TIMEOUT_SECONDS = 90.0


def _print(value: dict[str, object], *, stderr: bool = False) -> None:
    print(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True),
        file=sys.stderr if stderr else sys.stdout,
    )


async def _wait_until(predicate, timeout_seconds: float) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError("condition timed out")
        await asyncio.sleep(0.02)


async def _operator_confirm() -> bool | None:
    preset = os.environ.get("GATE6_3_4_BARGE_IN_CONFIRM", "").strip().lower()
    if preset in {"1", "y", "yes", "true"}:
        return True
    if preset in {"0", "n", "no", "false"}:
        return False
    if not sys.stdin.isatty():
        return None
    answer = await asyncio.to_thread(
        input,
        "旧回复是否立即停止，并且助手是否识别并回答了插话内容？输入 y 确认：",
    )
    return answer.strip().lower() in {"y", "yes"}


async def _run() -> int:
    paths = AppPaths.resolve(root_override=os.environ.get("NOTE_ASSISTANT_DATA_ROOT") or None)
    paths.ensure_directories()
    runtime = create_assistant_runtime(paths)
    controller = runtime.controller
    supervisor = runtime.audio_session_supervisor
    barge = runtime.acoustic_barge_in
    initial_trigger_count = 0
    promoted_capture_generation = 0
    operator_confirmed: bool | None = None
    failure_stage = "startup"
    try:
        await controller.start()
        await supervisor.start()
        await barge.start()
        if not controller.state.enabled:
            await controller.enable_assistant()
        await controller.ensure_device_identity()

        failure_stage = "activation"
        await controller.run_real_activation()
        activated = await controller.wait_for_state(
            lambda state: state.activation.status
            in {
                AssistantActivationStatus.ACTIVATED,
                AssistantActivationStatus.REQUIRED,
                AssistantActivationStatus.FAILED,
            },
            timeout_seconds=ACTIVATION_TIMEOUT_SECONDS,
        )
        if activated.activation.status is not AssistantActivationStatus.ACTIVATED:
            _print(
                {
                    "status": "real_gate_blocked",
                    "failure_stage": failure_stage,
                    "message": activated.activation.message,
                }
            )
            return 2

        failure_stage = "connect"
        if not controller.state.is_connected:
            await controller.connect()
        connected = await controller.wait_for_state(
            lambda state: state.is_connected or state.error is not None,
            timeout_seconds=CONNECT_TIMEOUT_SECONDS,
        )
        if not connected.is_connected:
            _print(
                {
                    "status": "real_gate_blocked",
                    "failure_stage": failure_stage,
                    "message": connected.error.message if connected.error else "connect failed",
                }
            )
            return 2

        await controller.set_voice_interaction_mode(VoiceInteractionMode.STREAMING_CONVERSATION)
        await controller.set_streaming_barge_in_enabled(True)
        await barge.reconcile()
        if not barge.snapshot.available:
            _print(
                {
                    "status": "real_gate_blocked",
                    "failure_stage": "aec_backend",
                    "error_code": barge.snapshot.error_code or "aec_audio_processing_not_installed",
                }
            )
            return 2

        print("请先说一个会得到较长语音回复的命令，例如：详细介绍今天的工作安排。", flush=True)
        failure_stage = "first_capture"
        await controller.start_streaming_conversation(permission_granted=True)
        await controller.wait_for_state(
            lambda state: state.audio.status is AssistantAudioStatus.RECORDING
            or state.error is not None,
            timeout_seconds=CAPTURE_TIMEOUT_SECONDS,
        )

        failure_stage = "playback_monitor"
        await _wait_until(
            lambda: controller.playback_output_active and barge.snapshot.monitor_active,
            PLAYBACK_TIMEOUT_SECONDS,
        )
        initial_trigger_count = controller.state.conversation.barge_in_trigger_count
        print(
            "现在请在助手仍在说话时清晰说一句新命令，例如：停一下，记录明天十点开会。说完后保持安静。",
            flush=True,
        )

        failure_stage = "acoustic_barge_in"
        await _wait_until(
            lambda: controller.state.conversation.barge_in_trigger_count > initial_trigger_count,
            BARGE_IN_TIMEOUT_SECONDS,
        )
        promoted_capture_generation = controller.state.audio.capture_generation
        await controller.wait_for_state(
            lambda state: state.audio.status is AssistantAudioStatus.RECORDING
            or state.error is not None,
            timeout_seconds=CAPTURE_TIMEOUT_SECONDS,
        )

        failure_stage = "new_turn_response"
        await controller.wait_for_state(
            lambda state: (
                state.conversation.last_assistant_text is not None
                and state.conversation.barge_in_trigger_count > initial_trigger_count
            )
            or state.error is not None,
            timeout_seconds=RESPONSE_TIMEOUT_SECONDS,
        )
        operator_confirmed = await _operator_confirm()
        if operator_confirmed is None:
            _print(
                {
                    "status": "real_gate_blocked",
                    "failure_stage": "operator_confirmation_required",
                    "message": "rerun interactively and confirm the audible interruption",
                }
            )
            return 2

        await controller.stop_streaming_conversation("gate6_3_4_real_complete")
        await _wait_until(
            lambda: not controller.state.conversation.streaming_session_active,
            12.0,
        )
        await barge.reconcile()
        snapshot = barge.snapshot
        verified = bool(
            operator_confirmed
            and controller.state.error is None
            and controller.state.conversation.barge_in_trigger_count == initial_trigger_count + 1
            and controller.barge_playback_cancel_count == 1
            and controller.barge_abort_count == 1
            and promoted_capture_generation > 0
            and not controller.playback_output_active
            and not controller.audio_capture_active
            and not snapshot.monitor_active
            and snapshot.monitor_uploaded_frames == 0
        )
        _print(
            {
                "status": "real_gate_complete" if verified else "failed",
                "failure_stage": None if verified else "terminal_verification",
                "operator_confirmed": operator_confirmed,
                "barge_in_trigger_count": controller.state.conversation.barge_in_trigger_count,
                "playback_cancel_count": controller.barge_playback_cancel_count,
                "abort_count": controller.barge_abort_count,
                "promoted_capture_generation": promoted_capture_generation,
                "processed_frames": snapshot.processed_frames,
                "render_frames": snapshot.render_frames,
                "aec_effective": snapshot.aec_effective,
                "ns_effective": snapshot.ns_effective,
                "agc_effective": snapshot.agc_effective,
                "monitor_uploaded_frames": snapshot.monitor_uploaded_frames,
                "terminal_monitor_active": snapshot.monitor_active,
                "terminal_audio_capture_active": controller.audio_capture_active,
                "terminal_playback_output_active": controller.playback_output_active,
                "payload_persisted": False,
                "pcm_persisted": False,
            }
        )
        return 0 if verified else 1
    except Exception as exc:
        _print(
            {
                "status": "failed",
                "failure_stage": failure_stage,
                "error_type": type(exc).__name__,
                "message": redact_error_text(str(exc) or type(exc).__name__),
                "barge_in": barge.diagnostics(),
            },
            stderr=True,
        )
        return 1
    finally:
        await barge.close()
        await runtime.offline_kws.close()
        await controller.shutdown()
        await supervisor.close()


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
