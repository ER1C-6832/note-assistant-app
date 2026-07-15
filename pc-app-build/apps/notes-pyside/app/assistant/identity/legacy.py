"""Import the already-authorized identity from the legacy py-xiaozhi client."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .models import DeviceIdentity


@dataclass(slots=True)
class LegacyPyXiaozhiIdentitySource:
    """Read-only migration source for the former PC Xiaozhi runtime."""

    config_dir: Path
    imported_from: Path | None = None
    local_activation_marked: bool = False

    @classmethod
    def from_local_app_data(
        cls,
        local_app_data: str | Path | None = None,
    ) -> "LegacyPyXiaozhiIdentitySource":
        configured = (
            str(local_app_data).strip()
            if local_app_data is not None
            else os.environ.get("LOCALAPPDATA", "").strip()
        )
        base = Path(configured).expanduser() if configured else Path.home() / "AppData" / "Local"
        return cls(config_dir=base / "py-xiaozhi" / "config")

    def load(self) -> DeviceIdentity | None:
        efuse_path = self.config_dir / "efuse.json"
        config_path = self.config_dir / "config.json"
        if not efuse_path.is_file() or not config_path.is_file():
            return None

        efuse = _read_object(efuse_path)
        config = _read_object(config_path)
        if efuse is None or config is None:
            return None

        system_options = config.get("SYSTEM_OPTIONS")
        if not isinstance(system_options, dict):
            return None

        device_id = _clean_text(system_options.get("DEVICE_ID")) or _clean_text(
            efuse.get("mac_address")
        )
        client_id = _clean_text(system_options.get("CLIENT_ID"))
        serial_number = _clean_text(efuse.get("serial_number"))
        hmac_key = _clean_text(efuse.get("hmac_key"))
        if not all((device_id, client_id, serial_number, hmac_key)):
            return None

        self.imported_from = self.config_dir
        self.local_activation_marked = bool(efuse.get("activation_status", False))
        return DeviceIdentity(
            device_id=_normalize_mac(device_id),
            client_id=client_id,
            serial_number=serial_number,
            hmac_key=hmac_key,
            generation=1,
        )


def _read_object(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _clean_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _normalize_mac(value: str) -> str:
    compact = "".join(character for character in value if character.isalnum()).lower()
    if len(compact) != 12:
        return value.strip().lower()
    return ":".join(compact[index : index + 2] for index in range(0, 12, 2))
