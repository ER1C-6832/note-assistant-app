"""Verify real user-stop precedence while a Gate 4 TTS response is playing."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.app_paths import AppPaths  # noqa: E402
from app.assistant import (  # noqa: E402
    AssistantActivationStatus,
    AssistantAudioStatus,
    AssistantController,
    AssistantState,
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
STOP_TIMEOUT_SECONDS = 12.0


class MonotonicClock:
    def now_ns(self) -> int:
        return time.perf_counter_ns()


def _optional_env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def _interrupt_delay_seconds() -> float:
    raw = _optional_env("GATE4_4_INTERRUPT_DELAY_SECONDS")
    try:
        value = float(raw) if raw is not None else 0.35
    except ValueError:
        value = 0.35
    return min(3.0, max(0.05, value))


def _response_timeout_seconds() -> float:
    raw = _optional_env("GATE4_4_RESPONSE_TIMEOUT_SECONDS")
    try:
        value = float(raw) if raw is not None else 90.0
    except ValueError:
        value = 90.0
    return min(180.0, max(30.0, value))


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


async def _confirm_interruption() -> bool | None:
    preset = (_optional_env("GATE4_4_STOP_CONFIRM") or "").lower()
    if preset in {"1", "y", "yes", "true"}:
        return True
    if preset in {"0", "n", "no", "false"}:
        return False
    if not sys.stdin.isatty():
        return None
    answer = await asyncio.to_thread(
        input,
        "是否听到回复开始后被中止，且没有自动重新开麦？输入 y 确认：",
    )
    return answer.strip().lower() in {"y", "yes"}


async def _wait_resources_closed(controller, timeout_seconds: float) -> bool:
    deadline = time.perf_counter() + timeout_seconds
    while time.perf_counter() < deadline:
        if (
            not controller.playback_output_active
            and not controller.playback_task_running
            and controller.playback_pcm_buffered_bytes == 0
            and not controller.audio_capture_active
            and not controller.audio_uplink_running
            and not controller.streaming_vad_running
        ):
            return True
        await asyncio.sleep(0.01)
    return False


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
    response_timeout_seconds = _response_timeout_seconds()
    initial_state = AssistantState.disabled(now_ns=clock.now_ns())
    initial_state = replace(
        initial_state,
        conversation=replace(
            initial_state.conversation,
            streaming_response_timeout_ms=int(response_timeout_seconds * 1_000),
        ),
    )
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
        initial_state=initial_state,
    )
    failure_stage: str | None = None
    final_state = controller.state
    confirmed: bool | None = None
    overlap_count = 0
    monitor_stop = asyncio.Event()

    async def monitor_overlap() -> None:
        nonlocal overlap_count
        while not monitor_stop.is_set():
            if controller.playback_output_active and controller.audio_capture_active:
                overlap_count += 1
            await asyncio.sleep(0.002)

    monitor_task = asyncio.create_task(monitor_overlap(), name="gate4-4-overlap-monitor")
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
            "请清楚说一句会产生较长回复的命令，例如：请用十句话介绍北京。"
            "说完后保持安静；回复开始播放后，runner 会自动执行用户 stop。",
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

        failure_stage = "playback_start"
        playing = await controller.wait_for_state(
            lambda state: state.audio.status is AssistantAudioStatus.PLAYING
            or state.error is not None,
            timeout_seconds=response_timeout_seconds + 30.0,
        )
        if playing.audio.status is not AssistantAudioStatus.PLAYING:
            message = playing.error.message if playing.error else "playback did not start"
            response_timeout = bool(
                playing.error is not None and playing.error.code == "streaming_response_timeout"
            )
            blocked = response_timeout or _environment_blocked(message)
            _print(
                {
                    "status": "real_gate_blocked" if blocked else "failed",
                    "failure_stage": failure_stage,
                    "message": message,
                    "response_timeout_seconds": response_timeout_seconds,
                    "retry_hint": (
                        "请确认已清楚说完命令并保持安静后重试" if response_timeout else None
                    ),
                }
            )
            return 2 if blocked else 1

        playback_generation = playing.audio.playback_generation
        turn_token = playing.conversation.last_completed_streaming_turn_token or 1
        auto_requests_before_stop = controller.auto_next_turn_request_count
        await asyncio.sleep(_interrupt_delay_seconds())
        if not controller.playback_output_active:
            _print(
                {
                    "status": "failed",
                    "failure_stage": "response_too_short",
                    "message": "playback drained before stop; retry with a longer response",
                }
            )
            return 1

        failure_stage = "stop_during_playback"
        await controller.stop_streaming_conversation("gate4_4_user_stop_during_playback")
        final_state = await controller.wait_for_state(
            lambda state: not state.conversation.streaming_session_active
            or state.error is not None,
            timeout_seconds=STOP_TIMEOUT_SECONDS,
        )
        resources_closed = await _wait_resources_closed(controller, STOP_TIMEOUT_SECONDS)
        confirmed = await _confirm_interruption()
        if confirmed is None:
            _print(
                {
                    "status": "real_gate_blocked",
                    "failure_stage": "operator_confirmation_required",
                    "message": (
                        "interactive interruption confirmation required; set "
                        "GATE4_4_STOP_CONFIRM=1 only after listening"
                    ),
                }
            )
            return 2

        cancelled_summary = final_state.audio.last_audio_summary or ""
        verified_before_shutdown = bool(
            confirmed
            and final_state.error is None
            and not final_state.conversation.streaming_session_active
            and resources_closed
            and controller.auto_next_turn_request_count == auto_requests_before_stop
            and controller.playback_last_summary is None
            and cancelled_summary.startswith("playback_cancelled")
            and overlap_count == 0
        )
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
                "failure_stage": None if verified else "stop_verification",
                "audible_interruption_confirmed": confirmed,
                "connection_generation": final_state.connection.connection_generation,
                "playback_generation": playback_generation,
                "turn_token": turn_token,
                "last_audio_summary": cancelled_summary,
                "natural_playback_summary_created": controller.playback_last_summary is not None,
                "auto_next_turn_request_count_before_stop": auto_requests_before_stop,
                "auto_next_turn_request_count_after_stop": (
                    controller.auto_next_turn_request_count
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
                "message": "Gate 4.4 stop-during-playback acceptance timed out",
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
