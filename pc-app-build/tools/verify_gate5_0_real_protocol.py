"""Verify Real Xiaozhi initialize + tools/list against the Gate 5.0 MCP runtime."""

from __future__ import annotations

import asyncio
import hashlib
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
from app.assistant.mcp import (  # noqa: E402
    FROZEN_GATE5_TOOL_NAMES,
    McpLifecycleSummary,
)
from app.assistant.network import ScriptedFakeTransport  # noqa: E402
from app.assistant.runtime_config import (  # noqa: E402
    DEFAULT_ASSISTANT_ACTIVATION_VERSION,
    DEFAULT_ASSISTANT_AUTHORIZATION_URL,
    DEFAULT_ASSISTANT_OTA_URL,
)

ACTIVATION_TIMEOUT_SECONDS = 25.0
CONNECT_TIMEOUT_SECONDS = 20.0
MCP_PROBE_TIMEOUT_SECONDS = 30.0


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


def _blocked(message: str) -> bool:
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
            "urlopen error",
            "ssl",
            "unexpected_eof_while_reading",
            "eof occurred in violation",
        )
    )


def _name_set_hash() -> str:
    canonical = "\n".join(sorted(FROZEN_GATE5_TOOL_NAMES)).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


async def _wait_for_protocol_methods(
    coordinator,
) -> dict[str, McpLifecycleSummary]:
    async with asyncio.timeout(MCP_PROBE_TIMEOUT_SECONDS):
        while True:
            summaries = {item.method: item for item in coordinator.lifecycle_history}
            if {"initialize", "tools/list"}.issubset(summaries):
                return summaries
            await asyncio.sleep(0.05)


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
        real_activation_client=RealOtaActivationClient(
            config_store=config_store,
            identity_manager=identity_manager,
        ),
    )
    state = controller.state
    summaries: dict[str, McpLifecycleSummary] = {}
    try:
        await controller.enable_assistant()
        await controller.ensure_device_identity()
        await controller.run_real_activation()
        activated = await controller.wait_for_state(
            lambda current: current.activation.status
            in {
                AssistantActivationStatus.ACTIVATED,
                AssistantActivationStatus.REQUIRED,
                AssistantActivationStatus.FAILED,
            },
            timeout_seconds=ACTIVATION_TIMEOUT_SECONDS,
        )
        if activated.activation.status is AssistantActivationStatus.REQUIRED:
            print(
                json.dumps(
                    {
                        "status": "real_gate_blocked",
                        "failure_stage": "activation_required",
                        "message": activated.activation.message,
                    },
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 2
        if activated.activation.status is not AssistantActivationStatus.ACTIVATED:
            message = activated.error.message if activated.error else activated.activation.message
            print(
                json.dumps(
                    {
                        "status": ("real_gate_blocked" if _blocked(message) else "failed"),
                        "failure_stage": "activation",
                        "message": redact_error_text(message),
                    },
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 2 if _blocked(message) else 1

        await controller.connect()
        state = await controller.wait_for_state(
            lambda current: current.is_connected or current.error is not None,
            timeout_seconds=CONNECT_TIMEOUT_SECONDS,
        )
        if not state.is_connected:
            message = state.error.message if state.error else "connect failed"
            print(
                json.dumps(
                    {
                        "status": ("real_gate_blocked" if _blocked(message) else "failed"),
                        "failure_stage": "connect",
                        "message": redact_error_text(message),
                    },
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 2 if _blocked(message) else 1

        try:
            summaries = await _wait_for_protocol_methods(real_transport.mcp_coordinator)
        except TimeoutError:
            print(
                json.dumps(
                    {
                        "status": "real_gate_blocked",
                        "failure_stage": "server_mcp_probe_timeout",
                        "message": (
                            "connected endpoint did not issue both initialize and tools/list "
                            f"within {MCP_PROBE_TIMEOUT_SECONDS:g} seconds"
                        ),
                        "observed_methods": sorted(
                            {
                                item.method
                                for item in real_transport.mcp_coordinator.lifecycle_history
                            }
                        ),
                    },
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 2

        verified = all(
            summaries[method].status == "success" for method in ("initialize", "tools/list")
        )
        before_disconnect = {
            "worker_alive": real_transport.mcp_coordinator.worker_alive,
            "request_queue_size": real_transport.mcp_coordinator.request_queue_size,
            "inflight_request_count": real_transport.mcp_coordinator.inflight_request_count,
            "response_future_count": real_transport.mcp_coordinator.response_future_count,
        }
        await controller.disconnect("gate5_0_real_protocol_complete")
        await controller.wait_for_state(
            lambda current: not current.is_connected,
            timeout_seconds=10.0,
        )
    finally:
        await controller.shutdown()
        await asyncio.sleep(0)

    pending = sorted(
        task.get_name()
        for task in asyncio.all_tasks()
        if task is not asyncio.current_task()
        and not task.done()
        and task.get_name().startswith("assistant-")
    )
    terminal = {
        "worker_alive": real_transport.mcp_coordinator.worker_alive,
        "request_queue_size": real_transport.mcp_coordinator.request_queue_size,
        "inflight_request_count": real_transport.mcp_coordinator.inflight_request_count,
        "dedupe_waiter_count": real_transport.mcp_coordinator.dedupe_waiter_count,
        "response_future_count": real_transport.mcp_coordinator.response_future_count,
    }
    verified = (
        verified and pending == [] and all(value in {0, False} for value in terminal.values())
    )
    print(
        json.dumps(
            {
                "status": "real_gate_complete" if verified else "failed",
                "websocket_url": state.connection.websocket_url_public,
                "connection_generation": state.connection.connection_generation,
                "session_id_masked": _mask(state.connection.session_id),
                "device_id_masked": identity.device_id_masked,
                "client_id_masked": identity.client_id_masked,
                "observed_methods": sorted(summaries),
                "observed_statuses": {
                    method: summaries[method].status for method in sorted(summaries)
                },
                "initialize_verified": summaries.get("initialize") is not None
                and summaries["initialize"].status == "success",
                "tools_list_verified": summaries.get("tools/list") is not None
                and summaries["tools/list"].status == "success",
                "tool_count": len(FROZEN_GATE5_TOOL_NAMES),
                "tool_name_set_sha256": _name_set_hash(),
                "before_disconnect": before_disconnect,
                "terminal": terminal,
                "pending_assistant_tasks": pending,
                "payload_persisted": False,
                "secrets_redacted": True,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if verified else 1


def main() -> int:
    try:
        return asyncio.run(_run())
    except TimeoutError:
        print(
            json.dumps(
                {
                    "status": "real_gate_blocked",
                    "failure_stage": "timeout",
                    "message": "Gate 5.0 Real protocol probe timed out",
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    except Exception as exc:
        message = redact_error_text(str(exc) or type(exc).__name__)
        blocked = _blocked(message)
        print(
            json.dumps(
                {
                    "status": "real_gate_blocked" if blocked else "failed",
                    "error_type": type(exc).__name__,
                    "message": message,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2 if blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
