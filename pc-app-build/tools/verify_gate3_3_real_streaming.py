"""Run Gate 3.3 Real streaming/VAD acceptance with one spoken command."""

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
    StreamingConversationState,
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
from app.assistant.protocol import has_readable_transcript_text  # noqa: E402
from app.assistant.runtime_config import (  # noqa: E402
    DEFAULT_ASSISTANT_ACTIVATION_VERSION,
    DEFAULT_ASSISTANT_AUTHORIZATION_URL,
    DEFAULT_ASSISTANT_OTA_URL,
)

ACTIVATION_TIMEOUT_SECONDS = 25.0
CONNECT_TIMEOUT_SECONDS = 20.0
STREAMING_RESPONSE_TIMEOUT_SECONDS = 55.0
STREAMING_START_TIMEOUT_SECONDS = 10.0
MAX_PUBLIC_TEXT_CHARS = 160


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
            "could not initialize libopus",
            "default input device",
            "invalid input device",
            "device unavailable",
            "no default input",
            "unanticipated host error",
        )
    )


def _activation_terminal(state) -> bool:
    return state.activation.status in {
        AssistantActivationStatus.ACTIVATED,
        AssistantActivationStatus.REQUIRED,
        AssistantActivationStatus.FAILED,
    }


def _mask(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}***{value[-4:]}"


def _public_text(value: str | None) -> str | None:
    return value[:MAX_PUBLIC_TEXT_CHARS] if value else None


def _print(payload: dict[str, object], *, stderr: bool = False) -> None:
    print(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        file=sys.stderr if stderr else sys.stdout,
    )


def _result(
    *,
    state,
    identity,
    paths: AppPaths,
    status: str,
    failure_stage: str | None,
    controller: AssistantController | None = None,
    pending_tasks: list[str] | None = None,
    local_session_id: str | None = None,
) -> dict[str, object]:
    return {
        "status": status,
        "failure_stage": failure_stage,
        "phase": state.phase.value,
        "identity_source": identity.source,
        "device_id_masked": identity.device_id_masked,
        "client_id_masked": identity.client_id_masked,
        "session_id_masked": _mask(state.connection.session_id),
        "streaming_session_id_masked": _mask(local_session_id),
        "websocket_url": state.connection.websocket_url_public,
        "streaming_generation": state.conversation.streaming_generation,
        "streaming_turn_index": state.conversation.streaming_turn_index,
        "streaming_state": state.conversation.streaming_state.value,
        "streaming_session_active": state.conversation.streaming_session_active,
        "vad_state": state.conversation.vad_state.value,
        "vad_status_text": state.conversation.vad_status_text,
        "vad_speech_started_count": state.diagnostics.vad_speech_started_count,
        "vad_speech_ended_count": state.diagnostics.vad_speech_ended_count,
        "input_device": state.audio.input_device_public_name,
        "sample_rate_hz": 16000,
        "frame_duration_ms": 20,
        "captured_frames": state.audio.captured_frames,
        "encoded_frames": state.audio.encoded_frames,
        "uploaded_frames": state.audio.uploaded_frames,
        "dropped_pcm_frames": state.audio.dropped_pcm_frames,
        "uplink_overflow_count": state.audio.uplink_overflow_count,
        "first_pcm_latency_ms": state.audio.first_pcm_latency_ms,
        "first_opus_latency_ms": state.audio.first_opus_latency_ms,
        "first_opus_upload_latency_ms": state.audio.first_opus_upload_latency_ms,
        "stop_listen_latency_ms": state.audio.stop_listen_latency_ms,
        "stt_text": _public_text(state.conversation.last_stt_text),
        "assistant_text": _public_text(state.conversation.last_assistant_text),
        "assistant_source_type": state.conversation.last_assistant_source_type,
        "real_handshake_verified": state.diagnostics.gate_real_handshake_verified,
        "real_audio_upload_verified": state.diagnostics.gate_real_audio_upload_verified,
        "real_streaming_uplink_verified": (state.diagnostics.gate_real_streaming_uplink_verified),
        "real_audio_response_verified": state.diagnostics.gate_real_audio_response_verified,
        "last_protocol_event": state.protocol.last_protocol_event,
        "error_code": state.error.code if state.error else None,
        "error_message": redact_error_text(state.error.message) if state.error else None,
        "audio_capture_active": controller.audio_capture_active if controller else False,
        "audio_uplink_running": controller.audio_uplink_running if controller else False,
        "streaming_vad_running": controller.streaming_vad_running if controller else False,
        "streaming_response_timer_running": (
            controller.streaming_response_timer_running if controller else False
        ),
        "audio_worker_alive": controller.audio_worker_alive if controller else False,
        "microphone_lease_generation": (
            controller.microphone_lease_generation if controller else None
        ),
        "pending_runtime_tasks": pending_tasks or [],
        "config_path": str(paths.assistant_runtime_config),
    }


async def _run() -> int:
    paths = AppPaths.resolve(root_override=_optional_env("NOTE_ASSISTANT_DATA_ROOT"))
    paths.ensure_directories()
    config_store = RuntimeConfigStore(paths.assistant_runtime_config)
    current = await asyncio.to_thread(config_store.load)
    await asyncio.to_thread(
        config_store.update_real_endpoints,
        ota_url=_optional_env("NOTE_ASSISTANT_OTA_URL")
        or current.real.ota_url
        or DEFAULT_ASSISTANT_OTA_URL,
        authorization_url=_optional_env("NOTE_ASSISTANT_AUTHORIZATION_URL")
        or current.real.authorization_url
        or DEFAULT_ASSISTANT_AUTHORIZATION_URL,
        activation_version=_optional_env("NOTE_ASSISTANT_ACTIVATION_VERSION")
        or current.real.activation_version
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
    audio_engine = AssistantAudioEngine(
        capture=PyAudioCaptureAdapter(),
        encoder_factory=PyAvOpusEncoder,
    )
    controller = AssistantController(
        transport=RuntimeTransportRouter(
            fake_transport=ScriptedFakeTransport(),
            real_transport=RealWebSocketTransport(config_provider=provider, clock=clock),
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
    identity = await identity_manager.ensure_identity()
    failure_stage: str | None = None
    accepted_state = controller.state
    local_session_id: str | None = None
    try:
        failure_stage = "activation"
        await controller.enable_assistant()
        await controller.ensure_device_identity()
        await controller.run_real_activation()
        activated = await controller.wait_for_state(
            _activation_terminal,
            timeout_seconds=ACTIVATION_TIMEOUT_SECONDS,
        )
        if activated.activation.status is AssistantActivationStatus.REQUIRED:
            _print(
                _result(
                    state=activated,
                    identity=identity,
                    paths=paths,
                    status="real_gate_blocked",
                    failure_stage="activation_required",
                    controller=controller,
                )
            )
            return 2
        if activated.activation.status is not AssistantActivationStatus.ACTIVATED:
            message = activated.error.message if activated.error else activated.activation.message
            blocked = _environment_blocked(message or "activation failed")
            _print(
                _result(
                    state=activated,
                    identity=identity,
                    paths=paths,
                    status="real_gate_blocked" if blocked else "failed",
                    failure_stage=failure_stage,
                    controller=controller,
                )
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
                _result(
                    state=connected,
                    identity=identity,
                    paths=paths,
                    status="real_gate_blocked" if blocked else "failed",
                    failure_stage=failure_stage,
                    controller=controller,
                )
            )
            return 2 if blocked else 1

        await controller.set_voice_interaction_mode(VoiceInteractionMode.STREAMING_CONVERSATION)
        print(
            "请开始说一句真实命令；说完后保持安静，VAD 将自动提交，例如：记录客户报价。",
            flush=True,
        )
        failure_stage = "streaming_start"
        await controller.start_streaming_conversation(permission_granted=True)
        recording = await controller.wait_for_state(
            lambda state: state.audio.status is AssistantAudioStatus.RECORDING
            or state.error is not None,
            timeout_seconds=STREAMING_START_TIMEOUT_SECONDS,
        )
        if recording.audio.status is not AssistantAudioStatus.RECORDING:
            message = (
                recording.error.message if recording.error else "streaming capture did not start"
            )
            blocked = _environment_blocked(message)
            _print(
                _result(
                    state=recording,
                    identity=identity,
                    paths=paths,
                    status="real_gate_blocked" if blocked else "failed",
                    failure_stage=failure_stage,
                    controller=controller,
                )
            )
            return 2 if blocked else 1

        local_session_id = recording.conversation.streaming_session_id
        turn_token = recording.conversation.active_streaming_turn_token
        if not local_session_id or turn_token is None:
            _print(
                _result(
                    state=recording,
                    identity=identity,
                    paths=paths,
                    status="failed",
                    failure_stage="streaming_identity_missing",
                    controller=controller,
                    local_session_id=local_session_id,
                )
            )
            return 1

        failure_stage = "vad_auto_submit_and_response"
        accepted_state = await controller.wait_for_state(
            lambda state: (
                state.conversation.last_completed_streaming_turn_token >= turn_token
                or (
                    state.conversation.streaming_state
                    is StreamingConversationState.WAITING_FOR_NEXT_TURN
                    and has_readable_transcript_text(state.conversation.last_assistant_text or "")
                    and not controller.audio_capture_active
                )
                or state.error is not None
            ),
            timeout_seconds=STREAMING_RESPONSE_TIMEOUT_SECONDS,
        )
        if accepted_state.conversation.streaming_session_active:
            await controller.stop_streaming_conversation("gate3_3_real_acceptance_complete")
            accepted_state = await controller.wait_for_state(
                lambda state: not state.conversation.streaming_session_active
                or state.error is not None,
                timeout_seconds=10.0,
            )

        readable_stt = has_readable_transcript_text(accepted_state.conversation.last_stt_text or "")
        readable_reply = has_readable_transcript_text(
            accepted_state.conversation.last_assistant_text or ""
        )
        verified_before_shutdown = bool(
            accepted_state.is_connected
            and accepted_state.audio.captured_frames > 0
            and accepted_state.audio.encoded_frames > 0
            and accepted_state.audio.uploaded_frames > 0
            and accepted_state.audio.uplink_overflow_count == 0
            and accepted_state.audio.stop_listen_latency_ms is not None
            and accepted_state.diagnostics.vad_speech_started_count > 0
            and accepted_state.diagnostics.vad_speech_ended_count > 0
            and accepted_state.diagnostics.gate_real_audio_upload_verified
            and accepted_state.diagnostics.gate_real_streaming_uplink_verified
            and accepted_state.diagnostics.gate_real_audio_response_verified
            and readable_stt
            and readable_reply
            and not accepted_state.conversation.streaming_session_active
            and not controller.audio_capture_active
            and not controller.audio_uplink_running
            and not controller.streaming_vad_running
            and not controller.streaming_response_timer_running
            and not controller.audio_worker_alive
            and controller.microphone_lease_generation is None
        )

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
            _result(
                state=accepted_state,
                identity=identity,
                paths=paths,
                status="real_gate_complete" if verified else "failed",
                failure_stage=None if verified else "streaming_verification",
                controller=controller,
                pending_tasks=pending,
                local_session_id=local_session_id,
            )
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
                "message": "Gate 3.3 Real streaming acceptance timed out",
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
