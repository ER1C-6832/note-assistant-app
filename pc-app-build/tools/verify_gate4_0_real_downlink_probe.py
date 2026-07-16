"""Run Gate 4.0 real downlink protocol probe without opening an output device."""

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
from app.assistant.network.downlink_probe import (  # noqa: E402
    MetadataOnlyDownlinkProbe,
)
from app.assistant.network.probing_websocket_transport import (  # noqa: E402
    ProbingRealWebSocketTransport,
)
from app.assistant.runtime_config import (  # noqa: E402
    DEFAULT_ASSISTANT_ACTIVATION_VERSION,
    DEFAULT_ASSISTANT_AUTHORIZATION_URL,
    DEFAULT_ASSISTANT_OTA_URL,
)

ACTIVATION_TIMEOUT_SECONDS = 25.0
CONNECT_TIMEOUT_SECONDS = 20.0
STREAMING_START_TIMEOUT_SECONDS = 10.0
PROBE_TIMEOUT_SECONDS = 60.0


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


def _print(payload: dict[str, object], *, stderr: bool = False) -> None:
    print(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        file=sys.stderr if stderr else sys.stdout,
    )


async def _wait_for_probe(probe: MetadataOnlyDownlinkProbe, controller) -> None:
    deadline = asyncio.get_running_loop().time() + PROBE_TIMEOUT_SECONDS
    while True:
        snapshot = probe.snapshot()
        if (
            snapshot.audio_format is not None
            and snapshot.binary_packet_count > 0
            and snapshot.decoded is not None
            and snapshot.observed_terminal
        ):
            return
        if controller.state.error is not None:
            raise RuntimeError(controller.state.error.message)
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError("Gate 4.0 real downlink probe timed out")
        await asyncio.sleep(0.05)


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
    probe = MetadataOnlyDownlinkProbe(packet_capacity=128)
    real_transport = ProbingRealWebSocketTransport(
        downlink_probe=probe,
        config_provider=provider,
        clock=clock,
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
        audio_engine=AssistantAudioEngine(
            capture=PyAudioCaptureAdapter(),
            encoder_factory=PyAvOpusEncoder,
        ),
        microphone_coordinator=MicrophoneLeaseCoordinator(),
    )

    try:
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
                    "payload_persisted": False,
                    "secrets_redacted": True,
                }
            )
            return 2
        if activated.activation.status is not AssistantActivationStatus.ACTIVATED:
            message = activated.error.message if activated.error else "activation failed"
            return _failure("activation", message)

        await controller.connect()
        connected = await controller.wait_for_state(
            lambda state: state.is_connected or state.error is not None,
            timeout_seconds=CONNECT_TIMEOUT_SECONDS,
        )
        if not connected.is_connected:
            message = connected.error.message if connected.error else "connect failed"
            return _failure("connect", message)

        await controller.set_voice_interaction_mode(VoiceInteractionMode.STREAMING_CONVERSATION)
        print(
            "请说一句真实命令；说完保持安静。此探测不会打开扬声器，也不会保存 Opus/PCM。",
            flush=True,
        )
        await controller.start_streaming_conversation(permission_granted=True)
        recording = await controller.wait_for_state(
            lambda state: state.audio.status is AssistantAudioStatus.RECORDING
            or state.error is not None,
            timeout_seconds=STREAMING_START_TIMEOUT_SECONDS,
        )
        if recording.audio.status is not AssistantAudioStatus.RECORDING:
            message = recording.error.message if recording.error else "capture did not start"
            return _failure("streaming_start", message)

        await _wait_for_probe(probe, controller)
        before_shutdown = probe.snapshot()
        if controller.state.conversation.streaming_session_active:
            await controller.stop_streaming_conversation("gate4_0_probe_complete")
            await controller.wait_for_state(
                lambda state: not state.conversation.streaming_session_active
                or state.error is not None,
                timeout_seconds=10.0,
            )

        await controller.shutdown()
        await asyncio.sleep(0)
        final_snapshot = probe.snapshot()
        pending = sorted(
            task.get_name()
            for task in asyncio.all_tasks()
            if task is not asyncio.current_task()
            and not task.done()
            and task.get_name().startswith("assistant-")
        )
        verified = bool(
            before_shutdown.audio_format is not None
            and before_shutdown.audio_params_error is None
            and before_shutdown.binary_packet_count > 0
            and before_shutdown.decoded is not None
            and before_shutdown.observed_terminal
            and before_shutdown.queue_overflow_count == 0
            and before_shutdown.payload_persisted is False
            and final_snapshot.task_running is False
            and pending == []
        )
        result = before_shutdown.as_public_dict()
        result.update(
            {
                "status": "real_gate_complete" if verified else "failed",
                "failure_stage": None if verified else "probe_verification",
                "output_device_opened": False,
                "pending_assistant_tasks": pending,
                "probe_task_running_at_final": final_snapshot.task_running,
            }
        )
        _print(result)
        return 0 if verified else 1
    finally:
        if not controller.closed:
            await controller.shutdown()
            await asyncio.sleep(0)


def _failure(stage: str, message: str) -> int:
    clean = redact_error_text(message)
    blocked = _environment_blocked(clean)
    _print(
        {
            "status": "real_gate_blocked" if blocked else "failed",
            "failure_stage": stage,
            "message": clean,
            "payload_persisted": False,
            "secrets_redacted": True,
            "output_device_opened": False,
        },
        stderr=True,
    )
    return 2 if blocked else 1


def main() -> int:
    try:
        return asyncio.run(_run())
    except TimeoutError as exc:
        return _failure("timeout", str(exc))
    except Exception as exc:
        return _failure(type(exc).__name__, str(exc) or type(exc).__name__)


if __name__ == "__main__":
    raise SystemExit(main())
