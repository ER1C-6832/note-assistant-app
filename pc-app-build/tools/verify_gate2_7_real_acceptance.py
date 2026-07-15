"""Run the complete Gate 2.7 Real identity/OTA/WebSocket/text/recovery acceptance."""

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
    redact_error_text,
)
from app.assistant.identity import LegacyPyXiaozhiIdentitySource  # noqa: E402
from app.assistant.network import ScriptedFakeTransport  # noqa: E402
from app.assistant.protocol import has_readable_transcript_text  # noqa: E402
from app.assistant.runtime_config import (  # noqa: E402
    DEFAULT_ASSISTANT_ACTIVATION_VERSION,
    DEFAULT_ASSISTANT_AUTHORIZATION_URL,
    DEFAULT_ASSISTANT_OTA_URL,
)

DEFAULT_TEXT_PROMPT = "回复验收通过"
MAX_TEXT_PROMPT_CHARS = 10
CONNECT_TIMEOUT_SECONDS = 15.0
ACTIVATION_TIMEOUT_SECONDS = 20.0
TEXT_TIMEOUT_SECONDS = 45.0
RECOVERY_TIMEOUT_SECONDS = 30.0
ABNORMAL_CLOSE_CODE = 1012
ABNORMAL_CLOSE_REASON = "gate2_7_real_acceptance"
MAX_PUBLIC_REPLY_CHARS = 500


class MonotonicClock:
    def now_ns(self) -> int:
        return time.perf_counter_ns()


class CountingActivationClient:
    def __init__(self, delegate: RealOtaActivationClient) -> None:
        self._delegate = delegate
        self.calls = 0

    async def run(self):
        self.calls += 1
        return await self._delegate.run()


def _optional_env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def _resolve_text_prompt(value: str | None) -> str:
    """Keep the acceptance text within the service's ten-character wire limit."""

    prompt = (value or DEFAULT_TEXT_PROMPT).strip() or DEFAULT_TEXT_PROMPT
    return prompt[:MAX_TEXT_PROMPT_CHARS]


def _mask(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}***{value[-4:]}"


def _activation_terminal(state) -> bool:
    return state.activation.status in {
        AssistantActivationStatus.ACTIVATED,
        AssistantActivationStatus.REQUIRED,
        AssistantActivationStatus.FAILED,
    }


def _environment_blocked(message: str) -> bool:
    lowered = message.lower()
    return any(
        marker in lowered
        for marker in (
            "token 未配置",
            "websocket url 未配置",
            "activation required",
            "需要验证码激活",
            "等待用户完成",
            "网络请求失败",
            "service unavailable",
            "temporarily unavailable",
            "connection refused",
            "name or service not known",
            "nodename nor servname",
            "dns",
        )
    )


def _blocked_result(state, identity, paths: AppPaths, activation_calls: int) -> dict[str, object]:
    return {
        "status": "real_gate_blocked",
        "block_reason": "activation_required",
        "activation_status": state.activation.status.value,
        "activation_code": state.activation.activation_code,
        "authorization_url": state.activation.authorization_url,
        "activation_message": state.activation.message,
        "activation_calls": activation_calls,
        "device_id_masked": identity.device_id_masked,
        "client_id_masked": identity.client_id_masked,
        "identity_generation": identity.generation,
        "identity_source": identity.source,
        "config_path": str(paths.assistant_runtime_config),
    }


def _public_result(
    state,
    identity,
    paths: AppPaths,
    *,
    status: str,
    prompt: str,
    activation_calls: int,
    headers_verified: bool,
    first_generation: int,
    first_session: str | None,
    failure_stage: str | None = None,
) -> dict[str, object]:
    reply = state.conversation.last_assistant_text
    return {
        "status": status,
        "failure_stage": failure_stage,
        "phase": state.phase.value,
        "activation_status": state.activation.status.value,
        "activation_calls": activation_calls,
        "identity_ready": state.identity.identity_ready,
        "identity_generation": identity.generation,
        "identity_source": identity.source,
        "device_id_masked": identity.device_id_masked,
        "client_id_masked": identity.client_id_masked,
        "headers_verified": headers_verified,
        "authorization_header_present": headers_verified,
        "protocol_version": "1" if headers_verified else None,
        "websocket_url": state.connection.websocket_url_public,
        "first_generation": first_generation,
        "recovered_generation": state.connection.connection_generation,
        "generation_advanced": state.connection.connection_generation > first_generation,
        "first_session_id_masked": _mask(first_session),
        "recovered_session_id_masked": _mask(state.connection.session_id),
        "session_changed": bool(
            first_session
            and state.connection.session_id
            and first_session != state.connection.session_id
        ),
        "forced_close_code": ABNORMAL_CLOSE_CODE,
        "forced_close_reason": ABNORMAL_CLOSE_REASON,
        "prompt_chars": len(prompt),
        "prompt_limit_chars": MAX_TEXT_PROMPT_CHARS,
        "assistant_text": reply[:MAX_PUBLIC_REPLY_CHARS] if reply else None,
        "assistant_source_type": state.conversation.last_assistant_source_type,
        "real_handshake_verified": state.diagnostics.gate_real_handshake_verified,
        "real_text_verified": state.diagnostics.gate_real_text_verified,
        "reconnect_attempt": state.recovery.reconnect_attempt,
        "next_reconnect_at_ns": state.recovery.next_reconnect_at_ns,
        "last_reconnect_decision": state.recovery.last_reconnect_decision,
        "last_protocol_event": state.protocol.last_protocol_event,
        "last_protocol_error": state.protocol.last_protocol_error,
        "error_code": state.error.code if state.error else None,
        "error_message": (redact_error_text(state.error.message) if state.error else None),
        "config_path": str(paths.assistant_runtime_config),
    }


def _print_result(payload: dict[str, object], *, stderr: bool = False) -> None:
    print(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        file=sys.stderr if stderr else sys.stdout,
    )


async def _run() -> int:
    data_root = _optional_env("NOTE_ASSISTANT_DATA_ROOT")
    prompt = _resolve_text_prompt(_optional_env("NOTE_ASSISTANT_GATE2_7_TEXT"))
    paths = AppPaths.resolve(root_override=data_root)
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

    compatibility_source = LegacyPyXiaozhiIdentitySource.from_local_app_data()
    identity_manager = DeviceIdentityManager(
        DeviceIdentityStore(config_store),
        legacy_identity=compatibility_source.load,
    )
    provider = PersistedConnectionConfigProvider(
        config_store=config_store,
        identity_manager=identity_manager,
    )
    clock = MonotonicClock()
    real_transport = RealWebSocketTransport(config_provider=provider, clock=clock)
    activation_client = CountingActivationClient(
        RealOtaActivationClient(
            config_store=config_store,
            identity_manager=identity_manager,
        )
    )
    controller = AssistantController(
        transport=RuntimeTransportRouter(
            fake_transport=ScriptedFakeTransport(),
            real_transport=real_transport,
        ),
        state_machine=ConversationStateMachine(ReconnectPolicy()),
        clock=clock,
        identity_manager=identity_manager,
        real_activation_client=activation_client,
    )

    first_generation = 0
    first_session: str | None = None
    identity = await identity_manager.ensure_identity()
    try:
        await controller.enable_assistant()
        await controller.ensure_device_identity()
        await controller.run_real_activation()
        activated = await controller.wait_for_state(
            _activation_terminal,
            timeout_seconds=ACTIVATION_TIMEOUT_SECONDS,
        )
        if activated.activation.status is AssistantActivationStatus.REQUIRED:
            _print_result(_blocked_result(activated, identity, paths, activation_client.calls))
            return 2
        if activated.activation.status is not AssistantActivationStatus.ACTIVATED:
            activation_message = activated.activation.message or (
                activated.error.message if activated.error else "activation failed"
            )
            blocked = _environment_blocked(activation_message)
            _print_result(
                _public_result(
                    activated,
                    identity,
                    paths,
                    status="real_gate_blocked" if blocked else "failed",
                    prompt=prompt,
                    activation_calls=activation_client.calls,
                    headers_verified=False,
                    first_generation=0,
                    first_session=None,
                    failure_stage="activation",
                )
            )
            return 2 if blocked else 1

        connection_config = await provider.load_real()
        connection_config.validate()
        headers = connection_config.headers()
        headers_verified = (
            set(headers) == {"Authorization", "Protocol-Version", "Device-Id", "Client-Id"}
            and headers["Authorization"].startswith("Bearer ")
            and headers["Protocol-Version"] == "1"
            and bool(headers["Device-Id"])
            and bool(headers["Client-Id"])
        )

        await controller.connect()
        connected = await controller.wait_for_state(
            lambda state: state.is_connected or state.error is not None,
            timeout_seconds=CONNECT_TIMEOUT_SECONDS,
        )
        if not connected.is_connected:
            connection_message = connected.error.message if connected.error else "connect failed"
            blocked = _environment_blocked(connection_message)
            _print_result(
                _public_result(
                    connected,
                    identity,
                    paths,
                    status="real_gate_blocked" if blocked else "failed",
                    prompt=prompt,
                    activation_calls=activation_client.calls,
                    headers_verified=headers_verified,
                    first_generation=0,
                    first_session=None,
                    failure_stage="connect",
                )
            )
            return 2 if blocked else 1

        await controller.send_text(prompt)
        submitted = controller.state
        turn_token = submitted.conversation.active_text_turn_token
        if turn_token is None:
            _print_result(
                _public_result(
                    submitted,
                    identity,
                    paths,
                    status="failed",
                    prompt=prompt,
                    activation_calls=activation_client.calls,
                    headers_verified=headers_verified,
                    first_generation=submitted.connection.connection_generation,
                    first_session=submitted.connection.session_id,
                    failure_stage="text_turn_not_started",
                )
            )
            return 1

        try:
            text_state = await controller.wait_for_state(
                lambda state: state.error is not None
                or state.diagnostics.gate_real_text_verified
                or state.conversation.last_completed_text_turn_token >= turn_token,
                timeout_seconds=TEXT_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            text_state = controller.state
            _print_result(
                _public_result(
                    text_state,
                    identity,
                    paths,
                    status="failed",
                    prompt=prompt,
                    activation_calls=activation_client.calls,
                    headers_verified=headers_verified,
                    first_generation=text_state.connection.connection_generation,
                    first_session=text_state.connection.session_id,
                    failure_stage="text_turn_timeout",
                )
            )
            return 1

        readable_reply = has_readable_transcript_text(
            text_state.conversation.last_assistant_text or ""
        )
        if not (
            text_state.is_connected
            and text_state.diagnostics.gate_real_handshake_verified
            and text_state.diagnostics.gate_real_text_verified
            and readable_reply
        ):
            _print_result(
                _public_result(
                    text_state,
                    identity,
                    paths,
                    status="failed",
                    prompt=prompt,
                    activation_calls=activation_client.calls,
                    headers_verified=headers_verified,
                    first_generation=text_state.connection.connection_generation,
                    first_session=text_state.connection.session_id,
                    failure_stage="text_turn_verification",
                )
            )
            return 1

        first_generation = text_state.connection.connection_generation
        first_session = text_state.connection.session_id
        await real_transport.force_abnormal_close_for_acceptance(
            first_generation,
            code=ABNORMAL_CLOSE_CODE,
            reason=ABNORMAL_CLOSE_REASON,
        )
        recovered = await controller.wait_for_state(
            lambda state: (
                state.is_connected and state.connection.connection_generation > first_generation
            )
            or (state.error is not None and state.error.code == "reconnect_exhausted"),
            timeout_seconds=RECOVERY_TIMEOUT_SECONDS,
        )
        verified = (
            headers_verified
            and activation_client.calls == 1
            and recovered.is_connected
            and recovered.connection.connection_generation > first_generation
            and recovered.connection.session_id is not None
            and recovered.connection.session_id != first_session
            and recovered.recovery.reconnect_attempt == 0
            and recovered.recovery.next_reconnect_at_ns is None
            and recovered.diagnostics.gate_real_handshake_verified
            and recovered.diagnostics.gate_real_text_verified
            and has_readable_transcript_text(recovered.conversation.last_assistant_text or "")
        )
        _print_result(
            _public_result(
                recovered,
                identity,
                paths,
                status="real_gate_complete" if verified else "failed",
                prompt=prompt,
                activation_calls=activation_client.calls,
                headers_verified=headers_verified,
                first_generation=first_generation,
                first_session=first_session,
                failure_stage=None if verified else "recovery_verification",
            )
        )
        if verified:
            await controller.disconnect("gate2_7_real_acceptance_complete")
            return 0
        return 1
    finally:
        await controller.shutdown()


def main() -> int:
    try:
        return asyncio.run(_run())
    except TimeoutError:
        _print_result(
            {
                "status": "failed",
                "error_type": "TimeoutError",
                "message": "Gate 2.7 真实总验收等待超时",
            },
            stderr=True,
        )
        return 1
    except Exception as exc:
        message = redact_error_text(str(exc) or type(exc).__name__)
        blocked = _environment_blocked(message)
        _print_result(
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
