"""Run one real Gate 2.2 OTA/activation step with redacted console output."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "apps" / "notes-pyside"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.app_paths import AppPaths  # noqa: E402
from app.assistant.activation import (  # noqa: E402
    ActivationOutcomeStatus,
    RealOtaActivationClient,
)
from app.assistant.identity import (  # noqa: E402
    DeviceIdentityManager,
    DeviceIdentityStore,
)
from app.assistant.runtime_config import RuntimeConfigStore  # noqa: E402


def _redact_message(message: str) -> str:
    sensitive_pattern = re.compile(
        r"(?i)(token|hmac|challenge|authorization|secret|key)\s*[:=]\s*[^\s,;]+"
    )
    return sensitive_pattern.sub(lambda match: f"{match.group(1)}=***", message)[:300]


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"缺少环境变量 {name}")
    return value


async def _run() -> int:
    ota_url = _required_env("NOTE_ASSISTANT_OTA_URL")
    authorization_url = _required_env("NOTE_ASSISTANT_AUTHORIZATION_URL")
    activation_version = os.environ.get("NOTE_ASSISTANT_ACTIVATION_VERSION", "v2").strip()
    data_root = os.environ.get("NOTE_ASSISTANT_DATA_ROOT", "").strip() or None

    paths = AppPaths.resolve(root_override=data_root)
    paths.ensure_directories()
    config_store = RuntimeConfigStore(paths.assistant_runtime_config)
    await asyncio.to_thread(
        config_store.update_real_endpoints,
        ota_url=ota_url,
        authorization_url=authorization_url,
        activation_version=activation_version,
    )
    identity_manager = DeviceIdentityManager(DeviceIdentityStore(config_store))
    identity = await identity_manager.ensure_identity()
    client = RealOtaActivationClient(
        config_store=config_store,
        identity_manager=identity_manager,
    )
    outcome = await client.run()

    public_result = {
        "status": outcome.status.value,
        "message": outcome.message,
        "websocket_url": outcome.websocket_url_public,
        "activation_code": outcome.activation_code,
        "authorization_url": outcome.authorization_url,
        "device_id_masked": identity.device_id_masked,
        "client_id_masked": identity.client_id_masked,
        "identity_generation": identity.generation,
        "config_path": str(paths.assistant_runtime_config),
    }
    print(json.dumps(public_result, ensure_ascii=False, indent=2, sort_keys=True))

    if outcome.status is ActivationOutcomeStatus.ACTIVATED:
        return 0
    if outcome.status is ActivationOutcomeStatus.REQUIRED:
        return 2
    return 1


def main() -> int:
    try:
        return asyncio.run(_run())
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
