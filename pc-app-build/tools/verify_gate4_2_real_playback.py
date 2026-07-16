"""Run Gate 4.2 real one-turn TTS playback acceptance on Windows."""

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
PLAYBACK_TIMEOUT_SECONDS = 75.0
STOP_TIMEOUT_SECONDS = 10.0


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
            "default output device",
            "output device",
            "device unavailable",
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
    preset = (_optional_env("GATE4_2_AUDIBLE_CONFIRM") or "").lower()
    if preset in {"1", "y", "yes", "true"}:
        return True
    if preset in {"0", "n", "no", "false"}:
        return False
    if not sys.stdin.isatty():
        return None
    answer = await asyncio.to_thread(
        input,
        "是否听到完整、非静音、速度和音调正常的助手回复？输入 y 确认：",
    )
    return answer.strip().lower() in {"y", "yes"}


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
    audible: bool | None = None
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
            "请说一句真实命令；说完保持安静。应用将播放一轮真实回复，但不会自动开启第二轮。",
            flush=True,
        )
        failure_stage = "capture_start"
        await controller.start_streaming_conversation(permission_granted=True)
        recording = await controller.wait_for_state(
            lambda state: state.audio.status is AssistantAudioStatus.RECORDING
            or state.error is not None,
            timeout_seconds=CAPTURE_START_TIMEOUT_SECONDS,
        )
        if recording.audio.status is not AssistantAudioStatus.RECORDING:
            message = recording.error.message if recording.error else "capture did not start"
            blocked = _environment_blocked(message)
            _print(
                {
                    "status": "real_gate_blocked" if blocked else "failed",
                    "failure_stage": failure_stage,
                    "message": message,
                }
            )
            return 2 if blocked else 1

        failure_stage = "real_playback"
        final_state = await controller.wait_for_state(
            lambda state: (
                state.diagnostics.gate_real_audio_playback_verified
                and controller.playback_last_summary is not None
                and state.audio.status is AssistantAudioStatus.IDLE
            )
            or state.error is not None,
            timeout_seconds=PLAYBACK_TIMEOUT_SECONDS,
        )
        if final_state.error is not None:
            message = final_state.error.message
            blocked = _environment_blocked(message)
            _print(
                {
                    "status": "real_gate_blocked" if blocked else "failed",
                    "failure_stage": failure_stage,
                    "message": message,
                }
            )
            return 2 if blocked else 1

        if final_state.conversation.streaming_session_active:
            await controller.stop_streaming_conversation("gate4_2_real_acceptance_complete")
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
                        "interactive audible confirmation required; set "
                        "GATE4_2_AUDIBLE_CONFIRM=1 only after listening"
                    ),
                    "playback": _summary_dict(controller.playback_last_summary),
                }
            )
            return 2

        summary = controller.playback_last_summary
        machine_verified = bool(
            summary
            and summary.natural_end
            and summary.encoded_packets_received > 0
            and summary.decoded_sample_frames > 0
            and summary.played_sample_frames > 0
            and summary.encoded_overflow_count == 0
            and summary.pcm_overflow_count == 0
            and not controller.playback_output_active
            and not controller.playback_task_running
            and controller.playback_pcm_buffered_bytes == 0
            and not controller.audio_capture_active
            and not controller.audio_uplink_running
            and not controller.streaming_vad_running
            and not final_state.conversation.streaming_session_active
        )
        verified_before_shutdown = machine_verified and audible
        await controller.shutdown()
        await asyncio.sleep(0)
        pending = sorted(
            task.get_name()
            for task in asyncio.all_tasks()
            if task is not asyncio.current_task()
            and not task.done()
            and task.get_name().startswith("assistant-")
        )
        verified = verified_before_shutdown and pending == []
        _print(
            {
                "status": "real_gate_complete" if verified else "failed",
                "failure_stage": None if verified else "playback_verification",
                "real_handshake_verified": final_state.diagnostics.gate_real_handshake_verified,
                "real_audio_upload_verified": final_state.diagnostics.gate_real_audio_upload_verified,
                "real_playback_verified": final_state.diagnostics.gate_real_audio_playback_verified,
                "audible_confirmed": audible,
                "playback": _summary_dict(summary),
                "latency_sample_ms": controller.playback_latency_sample,
                "audio_output_active_at_final": controller.playback_output_active,
                "playback_task_running_at_final": controller.playback_task_running,
                "pcm_buffered_bytes_at_final": controller.playback_pcm_buffered_bytes,
                "pending_assistant_tasks": pending,
                "payload_persisted": False,
            }
        )
        return 0 if verified else 1
    finally:
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
                "message": "Gate 4.2 real playback acceptance timed out",
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
