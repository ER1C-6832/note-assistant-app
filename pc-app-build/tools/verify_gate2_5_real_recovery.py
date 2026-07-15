"""Run the mandatory Gate 2.5 real WebSocket recovery acceptance check."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.app_paths import AppPaths  # noqa: E402
from app.assistant import (  # noqa: E402
    AssistantController,
    ConversationStateMachine,
    DeviceIdentityManager,
    DeviceIdentityStore,
    PersistedConnectionConfigProvider,
    RealWebSocketTransport,
    ReconnectPolicy,
    RuntimeConfigStore,
    RuntimeTransportRouter,
)
from app.assistant.identity import LegacyPyXiaozhiIdentitySource  # noqa: E402
from app.assistant.network import ScriptedFakeTransport  # noqa: E402

CONNECT_TIMEOUT_SECONDS = 15.0
RECOVERY_TIMEOUT_SECONDS = 30.0
ABNORMAL_CLOSE_CODE = 1012
ABNORMAL_CLOSE_REASON = "gate2_5_real_recovery"


class MonotonicClock:
    def now_ns(self) -> int:
        return time.perf_counter_ns()


def _optional_env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def _mask(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}***{value[-4:]}"


def _redact_message(message: str) -> str:
    pattern = re.compile(r"(?i)(token|authorization|hmac|challenge|secret|key)\s*[:=]\s*[^\s,;]+")
    return pattern.sub(lambda match: f"{match.group(1)}=***", message)[:500]


def _credentials_unavailable(message: str) -> bool:
    lowered = message.lower()
    return any(
        marker in lowered
        for marker in (
            "token 未配置",
            "websocket url 未配置",
            "activation",
            "尚未建立有效 session",
        )
    )


async def _run() -> int:
    data_root = _optional_env("NOTE_ASSISTANT_DATA_ROOT")
    paths = AppPaths.resolve(root_override=data_root)
    paths.ensure_directories()

    config_store = RuntimeConfigStore(paths.assistant_runtime_config)
    compatibility_source = LegacyPyXiaozhiIdentitySource.from_local_app_data()
    identity_manager = DeviceIdentityManager(
        DeviceIdentityStore(config_store),
        legacy_identity=compatibility_source.load,
    )
    identity = await identity_manager.ensure_identity()
    provider = PersistedConnectionConfigProvider(
        config_store=config_store,
        identity_manager=identity_manager,
    )
    clock = MonotonicClock()
    real_transport = RealWebSocketTransport(config_provider=provider, clock=clock)
    controller = AssistantController(
        transport=RuntimeTransportRouter(
            fake_transport=ScriptedFakeTransport(),
            real_transport=real_transport,
        ),
        state_machine=ConversationStateMachine(ReconnectPolicy()),
        clock=clock,
        identity_manager=identity_manager,
    )

    first_session: str | None = None
    first_generation = 0
    try:
        await controller.enable_assistant()
        await controller.ensure_device_identity()
        await controller.connect()
        first = await controller.wait_for_state(
            lambda snapshot: snapshot.is_connected or snapshot.error is not None,
            timeout_seconds=CONNECT_TIMEOUT_SECONDS,
        )
        if not first.is_connected:
            message = first.error.message if first.error else "真实 WebSocket 未连接"
            print(
                json.dumps(
                    _public_result(
                        first,
                        identity,
                        paths,
                        status="failed",
                        first_generation=None,
                        first_session=None,
                    ),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 2 if _credentials_unavailable(message) else 1

        first_session = first.connection.session_id
        first_generation = first.connection.connection_generation
        await real_transport.force_abnormal_close_for_acceptance(
            first_generation,
            code=ABNORMAL_CLOSE_CODE,
            reason=ABNORMAL_CLOSE_REASON,
        )

        recovered = await controller.wait_for_state(
            lambda snapshot: (
                snapshot.is_connected
                and snapshot.connection.connection_generation > first_generation
            )
            or (snapshot.error is not None and snapshot.error.code == "reconnect_exhausted"),
            timeout_seconds=RECOVERY_TIMEOUT_SECONDS,
        )
        verified = (
            recovered.is_connected
            and recovered.connection.connection_generation > first_generation
            and recovered.connection.session_id is not None
            and recovered.recovery.reconnect_attempt == 0
            and recovered.recovery.next_reconnect_at_ns is None
            and recovered.diagnostics.gate_real_handshake_verified
        )
        print(
            json.dumps(
                _public_result(
                    recovered,
                    identity,
                    paths,
                    status="recovery_verified" if verified else "failed",
                    first_generation=first_generation,
                    first_session=first_session,
                ),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        if verified:
            await controller.disconnect("gate2_5_real_recovery_acceptance_complete")
            return 0
        return 1
    finally:
        await controller.shutdown()


def _public_result(
    state,
    identity,
    paths: AppPaths,
    *,
    status: str,
    first_generation: int | None,
    first_session: str | None,
) -> dict[str, object]:
    current_session = state.connection.session_id
    return {
        "status": status,
        "phase": state.phase.value,
        "websocket_url": state.connection.websocket_url_public,
        "device_id_masked": identity.device_id_masked,
        "client_id_masked": identity.client_id_masked,
        "identity_source": identity.source,
        "first_generation": first_generation,
        "recovered_generation": state.connection.connection_generation,
        "generation_advanced": (
            first_generation is not None
            and state.connection.connection_generation > first_generation
        ),
        "first_session_id_masked": _mask(first_session),
        "recovered_session_id_masked": _mask(current_session),
        "session_changed": bool(
            first_session and current_session and first_session != current_session
        ),
        "forced_close_code": ABNORMAL_CLOSE_CODE,
        "forced_close_reason": ABNORMAL_CLOSE_REASON,
        "reconnect_attempt": state.recovery.reconnect_attempt,
        "last_reconnect_decision": state.recovery.last_reconnect_decision,
        "next_reconnect_at_ns": state.recovery.next_reconnect_at_ns,
        "real_handshake_verified": state.diagnostics.gate_real_handshake_verified,
        "error_code": state.error.code if state.error else None,
        "error_message": _redact_message(state.error.message) if state.error else None,
        "config_path": str(paths.assistant_runtime_config),
    }


def main() -> int:
    try:
        return asyncio.run(_run())
    except asyncio.TimeoutError:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": "TimeoutError",
                    "message": "等待真实 WebSocket 自动恢复超时",
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "message": _redact_message(str(exc) or type(exc).__name__),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
