"""Run one real Gate 2.2 OTA/activation check with redacted console output."""

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
    LegacyPyXiaozhiIdentitySource,
)
from app.assistant.runtime_config import (  # noqa: E402
    DEFAULT_ASSISTANT_ACTIVATION_VERSION,
    DEFAULT_ASSISTANT_AUTHORIZATION_URL,
    DEFAULT_ASSISTANT_OTA_URL,
    RuntimeConfigStore,
)


def _redact_message(message: str) -> str:
    sensitive_pattern = re.compile(
        r"(?i)(token|hmac|challenge|authorization|secret|key)\s*[:=]\s*[^\s,;]+"
    )
    return sensitive_pattern.sub(lambda match: f"{match.group(1)}=***", message)[:300]


def _optional_env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


async def _run() -> int:
    data_root = _optional_env("NOTE_ASSISTANT_DATA_ROOT")
    paths = AppPaths.resolve(root_override=data_root)
    paths.ensure_directories()
    config_store = RuntimeConfigStore(paths.assistant_runtime_config)

    current = await asyncio.to_thread(config_store.load)
    ota_url = _optional_env("NOTE_ASSISTANT_OTA_URL") or current.real.ota_url
    authorization_url = (
        _optional_env("NOTE_ASSISTANT_AUTHORIZATION_URL") or current.real.authorization_url
    )
    activation_version = (
        _optional_env("NOTE_ASSISTANT_ACTIVATION_VERSION") or current.real.activation_version
    )
    await asyncio.to_thread(
        config_store.update_real_endpoints,
        ota_url=ota_url or DEFAULT_ASSISTANT_OTA_URL,
        authorization_url=authorization_url or DEFAULT_ASSISTANT_AUTHORIZATION_URL,
        activation_version=(activation_version or DEFAULT_ASSISTANT_ACTIVATION_VERSION),
    )

    had_current_identity = (await asyncio.to_thread(config_store.load)).identity is not None
    legacy_source = LegacyPyXiaozhiIdentitySource.from_local_app_data()
    identity_manager = DeviceIdentityManager(
        DeviceIdentityStore(config_store),
        legacy_identity=legacy_source.load,
    )
    identity = await identity_manager.ensure_identity()
    identity_source = (
        "legacy_py_xiaozhi"
        if legacy_source.imported_from is not None
        else "note_assistant_config" if had_current_identity else "new_identity"
    )

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
        "identity_source": identity_source,
        "legacy_local_activation_marked": (
            legacy_source.local_activation_marked
            if legacy_source.imported_from is not None
            else None
        ),
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
