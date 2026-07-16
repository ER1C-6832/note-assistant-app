"""Run Gate 4.3 real two-turn continuous-conversation acceptance on Windows."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.app_paths import AppPaths  # noqa: E402
from app.assistant import (  # noqa: E402
    AssistantActivationStatus,
    AssistantAudioStatus,
    AssistantController,
    ConversationStateMachine,
    DeviceIdentityManager,
    DeviceIdentityStore,
    PersistedConnectionConfigProvider,
    RealOtaActivationClient,
    RealWebSocketTransport,
    ReconnectPolicy,
    RuntimeConfigStore,
    RuntimeTransportRouter,
    VoiceInteractionMode,
    redact_error_text,
)
from app.assistant.audio import (  # noqa: E402
    AssistantAudioEngine,
    MicrophoneLeaseCoordinator,
    PyAudioCaptureAdapter,
    PyAvOpusEncoder,
)
from app.assistant.identity import LegacyPyXiaozhiIdentitySource  # noqa: E402
from app.assistant.network import ScriptedFakeTransport  # noqa: E402
from app.assistant.runtime_config import (  # noqa: E402
    DEFAULT_ASSISTANT_ACTIVATION_VERSION,
    DEFAULT_ASSISTANT_AUTHORIZATION_URL,
    DEFAULT_ASSISTANT_OTA_URL,
)

ACTIVATION_TIMEOUT_SECONDS = 25.0
CONNECT_TIMEOUT_SECONDS = 20.0
CAPTURE_START_TIMEOUT_SECONDS = 10.0
TURN_TIMEOUT_SECONDS = 90.0
STOP_TIMEOUT_SECONDS = 12.0


class MonotonicClock:
    def now_ns(self) -> int:
        return time.perf_counter_ns()


def _optional_env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def _environment_blocked(message: str) -> bool:
    lowered = message.lower()
    return any(
        marker in lowered
        for marker in (
            "activation required",
            "需要验证码激活",
            "等待用户完成",
            "token 未配置",
            "websocket url 未配置",
            "network",
            "dns",
            "connection refused",
            "service unavailable",
            "pyaudio is not installed",
            "av is not installed",
            "default input device",
            "default output device",
            "input device",
            "output device",
            "device unavailable",
            "invalid input device",
            "invalid output device",
            "unanticipated host error",
        )
    )


def _print(payload: dict[str, object], *, stderr: bool = False) -> None:
    print(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        file=sys.stderr if stderr else sys.stdout,
    )


def _summary_dict(summary) -> dict[str, object]:
    if summary is None:
        return {}
    return {
        "connection_generation": summary.connection_generation,
        "stream_sequence": summary.stream_sequence,
        "playback_generation": summary.playback_generation,
        "turn_token": summary.turn_token,
        "streaming_generation": summary.streaming_generation,
        "reason": summary.reason,
        "natural_end": summary.natural_end,
        "encoded_packets_received": summary.encoded_packets_received,
        "encoded_bytes_received": summary.encoded_bytes_received,
        "decoded_sample_frames": summary.decoded_sample_frames,
        "played_sample_frames": summary.played_sample_frames,
        "encoded_overflow_count": summary.encoded_overflow_count,
        "pcm_overflow_count": summary.pcm_overflow_count,
        "pcm_underflow_count": summary.pcm_underflow_count,
        "buffer_peak_bytes": summary.buffer_peak_bytes,
        "output_device_public_name": summary.output_device_public_name,
    }


async def _confirm_audible() -> bool | None:
    preset = (_optional_env("GATE4_3_AUDIBLE_CONFIRM") or "").lower()
    if preset in {"1", "y", "yes", "true"}:
        return True
    if preset in {"0", "n", "no", "false"}:
        return False
    if not sys.stdin.isatty():
        return None
    answer = await asyncio.to_thread(
        input,
        "是否听到两轮完整、非静音、速度和音调正常的助手回复？输入 y 确认：",
    )
    return answer.strip().lower() in {"y", "yes"}


def _playback_ok(summary) -> bool:
    return bool(
        summary
        and summary.natural_end
        and summary.encoded_packets_received > 0
        and summary.decoded_sample_frames > 0
        and summary.played_sample_frames == summary.decoded_sample_frames
        and summary.encoded_overflow_count == 0
        and summary.pcm_overflow_count == 0
    )


async def _run() -> int:
    paths = AppPaths.resolve(root_override=_optional_env("NOTE_ASSISTANT_DATA_ROOT"))
    paths.ensure_directories()
    config_store = RuntimeConfigStore(paths.assistant_runtime_config)
    current_config = await asyncio.to_thread(config_store.load)
    await asyncio.to_thread(
        config_store.update_real_endpoints,
        ota_url=_optional_env("NOTE_ASSISTANT_OTA_URL")
        or current_config.real.ota_url
        or DEFAULT_ASSISTANT_OTA_URL,
        authorization_url=_optional_env("NOTE_ASSISTANT_AUTHORIZATION_URL")
        or current_config.real.authorization_url
        or DEFAULT_ASSISTANT_AUTHORIZATION_URL,
        activation_version=_optional_env("NOTE_ASSISTANT_ACTIVATION_VERSION")
        or current_config.real.activation_version
        or DEFAULT_ASSISTANT_ACTIVATION_VERSION,
    )
    legacy = LegacyPyXiaozhiIdentitySource.from_local_app_data()
    identity_manager = DeviceIdentityManager(
        DeviceIdentityStore(config_store),
        legacy_identity=legacy.load,
    )
    provider = PersistedConnectionConfigProvider(
        config_store=config_store,
        identity_manager=identity_manager,
    )
    clock = MonotonicClock()
    real_transport = RealWebSocketTransport(config_provider=provider, clock=clock)
    audio_engine = AssistantAudioEngine(
        capture=PyAudioCaptureAdapter(),
        encoder_factory=PyAvOpusEncoder,
    )
    controller = AssistantController(
        transport=RuntimeTransportRouter(
            fake_transport=ScriptedFakeTransport(),
            real_transport=real_transport,
        ),
        state_machine=ConversationStateMachine(ReconnectPolicy()),
        clock=clock,
        identity_manager=identity_manager,
        real_activation_client=RealOtaActivationClient(
            config_store=config_store,
            identity_manager=identity_manager,
        ),
        audio_engine=audio_engine,
        microphone_coordinator=MicrophoneLeaseCoordinator(),
    )
    failure_stage: str | None = None
    final_state = controller.state
    first_summary = None
    second_summary = None
    audible: bool | None = None
    overlap_count = 0
    monitor_stop = asyncio.Event()

    async def monitor_overlap() -> None:
        nonlocal overlap_count
        while not monitor_stop.is_set():
            if controller.playback_output_active and controller.audio_capture_active:
                overlap_count += 1
            await asyncio.sleep(0.002)

    monitor_task = asyncio.create_task(monitor_overlap(), name="gate4-3-overlap-monitor")
    try:
        failure_stage = "activation"
        await controller.enable_assistant()
        await controller.ensure_device_identity()
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
        if activated.activation.status is AssistantActivationStatus.REQUIRED:
            _print(
                {
                    "status": "real_gate_blocked",
                    "failure_stage": "activation_required",
                    "message": activated.activation.message,
                }
            )
            return 2
        if activated.activation.status is not AssistantActivationStatus.ACTIVATED:
            message = activated.error.message if activated.error else activated.activation.message
            blocked = _environment_blocked(message or "activation failed")
            _print(
                {
                    "status": "real_gate_blocked" if blocked else "failed",
                    "failure_stage": failure_stage,
                    "message": message,
                }
            )
            return 2 if blocked else 1

        failure_stage = "connect"
        await controller.connect()
        connected = await controller.wait_for_state(
            lambda state: state.is_connected or state.error is not None,
            timeout_seconds=CONNECT_TIMEOUT_SECONDS,
        )
        if not connected.is_connected:
            message = connected.error.message if connected.error else "connect failed"
            blocked = _environment_blocked(message)
            _print(
                {
                    "status": "real_gate_blocked" if blocked else "failed",
                    "failure_stage": failure_stage,
                    "message": message,
                }
            )
            return 2 if blocked else 1

        await controller.set_voice_interaction_mode(VoiceInteractionMode.STREAMING_CONVERSATION)
        print(
            "请说第一句真实命令；听到第一轮回复后不要点击开始按钮，应用会自动开麦。",
            flush=True,
        )
        failure_stage = "turn_1_capture_start"
        await controller.start_streaming_conversation(permission_granted=True)
        first_recording = await controller.wait_for_state(
            lambda state: (
                state.audio.status is AssistantAudioStatus.RECORDING
                and state.conversation.streaming_turn_index == 1
            )
            or state.error is not None,
            timeout_seconds=CAPTURE_START_TIMEOUT_SECONDS,
        )
        if first_recording.audio.status is not AssistantAudioStatus.RECORDING:
            message = (
                first_recording.error.message if first_recording.error else "capture did not start"
            )
            blocked = _environment_blocked(message)
            _print(
                {
                    "status": "real_gate_blocked" if blocked else "failed",
                    "failure_stage": failure_stage,
                    "message": message,
                }
            )
            return 2 if blocked else 1
        first_capture_generation = first_recording.audio.capture_generation
        first_turn_token = first_recording.conversation.active_streaming_turn_token

        failure_stage = "turn_1_playback_and_auto_next"
        second_recording = await controller.wait_for_state(
            lambda state: (
                state.audio.status is AssistantAudioStatus.RECORDING
                and state.conversation.streaming_turn_index == 2
                and controller.playback_last_summary is not None
                and controller.playback_last_summary.turn_token == first_turn_token
            )
            or state.error is not None,
            timeout_seconds=TURN_TIMEOUT_SECONDS,
        )
        if second_recording.error is not None:
            message = second_recording.error.message
            blocked = _environment_blocked(message)
            _print(
                {
                    "status": "real_gate_blocked" if blocked else "failed",
                    "failure_stage": failure_stage,
                    "message": message,
                }
            )
            return 2 if blocked else 1
        first_summary = controller.playback_last_summary
        first_auto_request_count = controller.auto_next_turn_request_count
        second_capture_generation = second_recording.audio.capture_generation
        second_turn_token = second_recording.conversation.active_streaming_turn_token
        print(
            "第二轮已由 actual PlaybackEnded 自动开始。请说第二句命令；听到回复后保持安静。",
            flush=True,
        )

        failure_stage = "turn_2_playback_and_auto_next"
        third_recording = await controller.wait_for_state(
            lambda state: (
                state.audio.status is AssistantAudioStatus.RECORDING
                and state.conversation.streaming_turn_index == 3
                and controller.playback_last_summary is not None
                and controller.playback_last_summary.turn_token == second_turn_token
            )
            or state.error is not None,
            timeout_seconds=TURN_TIMEOUT_SECONDS,
        )
        if third_recording.error is not None:
            message = third_recording.error.message
            blocked = _environment_blocked(message)
            _print(
                {
                    "status": "real_gate_blocked" if blocked else "failed",
                    "failure_stage": failure_stage,
                    "message": message,
                }
            )
            return 2 if blocked else 1
        second_summary = controller.playback_last_summary
        requests_before_stop = controller.auto_next_turn_request_count
        starts_before_stop = controller.auto_next_turn_started_count

        failure_stage = "manual_session_stop"
        await controller.stop_streaming_conversation("gate4_3_two_turn_acceptance_complete")
        final_state = await controller.wait_for_state(
            lambda state: not state.conversation.streaming_session_active
            or state.error is not None,
            timeout_seconds=STOP_TIMEOUT_SECONDS,
        )
        audible = await _confirm_audible()
        if audible is None:
            _print(
                {
                    "status": "real_gate_blocked",
                    "failure_stage": "operator_confirmation_required",
                    "message": (
                        "interactive two-turn audible confirmation required; set "
                        "GATE4_3_AUDIBLE_CONFIRM=1 only after listening"
                    ),
                    "turn_1_playback": _summary_dict(first_summary),
                    "turn_2_playback": _summary_dict(second_summary),
                }
            )
            return 2

        machine_verified = bool(
            _playback_ok(first_summary)
            and _playback_ok(second_summary)
            and first_auto_request_count == 1
            and requests_before_stop == 2
            and starts_before_stop == 2
            and first_capture_generation > 0
            and second_capture_generation == first_capture_generation + 1
            and first_turn_token is not None
            and second_turn_token == first_turn_token + 1
            and overlap_count == 0
            and final_state.error is None
            and not final_state.conversation.streaming_session_active
            and not controller.playback_output_active
            and not controller.playback_task_running
            and controller.playback_pcm_buffered_bytes == 0
            and not controller.audio_capture_active
            and not controller.audio_uplink_running
            and not controller.streaming_vad_running
        )
        verified_before_shutdown = machine_verified and audible
        await controller.shutdown()
        await asyncio.sleep(0)
        pending = sorted(
            task.get_name()
            for task in asyncio.all_tasks()
            if task is not asyncio.current_task()
            and task is not monitor_task
            and not task.done()
            and task.get_name().startswith("assistant-")
        )
        verified = verified_before_shutdown and pending == []
        _print(
            {
                "status": "real_gate_complete" if verified else "failed",
                "failure_stage": None if verified else "two_turn_verification",
                "real_handshake_verified": final_state.diagnostics.gate_real_handshake_verified,
                "real_audio_upload_verified": final_state.diagnostics.gate_real_audio_upload_verified,
                "real_playback_verified": final_state.diagnostics.gate_real_audio_playback_verified,
                "audible_confirmed": audible,
                "turn_1": {
                    "capture_generation": first_capture_generation,
                    "turn_token": first_turn_token,
                    "playback": _summary_dict(first_summary),
                },
                "turn_2": {
                    "capture_generation": second_capture_generation,
                    "turn_token": second_turn_token,
                    "playback": _summary_dict(second_summary),
                },
                "auto_next_turn_request_count_before_stop": requests_before_stop,
                "auto_next_turn_started_count_before_stop": starts_before_stop,
                "auto_next_turn_suppressed_count": controller.auto_next_turn_suppressed_count,
                "last_playback_to_capture_start_latency_ms": (
                    controller.auto_next_turn_last_latency_ms
                ),
                "capture_playback_overlap_count": overlap_count,
                "audio_output_active_at_final": controller.playback_output_active,
                "playback_task_running_at_final": controller.playback_task_running,
                "pcm_buffered_bytes_at_final": controller.playback_pcm_buffered_bytes,
                "pending_assistant_tasks": pending,
                "payload_persisted": False,
            }
        )
        return 0 if verified else 1
    finally:
        monitor_stop.set()
        await asyncio.gather(monitor_task, return_exceptions=True)
        if not controller.closed:
            await controller.shutdown()
            await asyncio.sleep(0)


def main() -> int:
    try:
        return asyncio.run(_run())
    except TimeoutError:
        _print(
            {
                "status": "failed",
                "failure_stage": "timeout",
                "message": "Gate 4.3 real two-turn acceptance timed out",
            },
            stderr=True,
        )
        return 1
    except Exception as exc:
        message = redact_error_text(str(exc) or type(exc).__name__)
        blocked = _environment_blocked(message)
        _print(
            {
                "status": "real_gate_blocked" if blocked else "failed",
                "error_type": type(exc).__name__,
                "message": message,
            },
            stderr=True,
        )
        return 2 if blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
