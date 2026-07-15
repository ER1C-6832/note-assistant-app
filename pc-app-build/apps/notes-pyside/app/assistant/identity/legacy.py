"""Read-only compatibility source for an already-authorized PC Xiaozhi identity."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .models import DeviceIdentity

LEGACY_APP_DIR_NAMES = (
    "py-xiaozhi",
    "py_xiaozhi",
    "xiaozhi",
    "py-xiaozhi-tao-analysis",
)


@dataclass(slots=True)
class LegacyPyXiaozhiIdentitySource:
    """Discover and import the former PC client's device identity without executing it."""

    config_dir: Path | None = None
    additional_config_dirs: tuple[Path, ...] = ()
    imported_from: Path | None = None
    local_activation_marked: bool | None = None
    searched_dirs: tuple[Path, ...] = field(default_factory=tuple)
    recovered_client_id: bool = False

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
        local_base = (
            Path(configured).expanduser() if configured else Path.home() / "AppData" / "Local"
        )
        candidates = _candidate_config_dirs(local_base=local_base)
        primary = candidates[0] if candidates else local_base / LEGACY_APP_DIR_NAMES[0] / "config"
        return cls(config_dir=primary, additional_config_dirs=tuple(candidates[1:]))

    def load(self) -> DeviceIdentity | None:
        candidates = _deduplicate_paths(
            (
                *((self.config_dir,) if self.config_dir is not None else ()),
                *self.additional_config_dirs,
            )
        )
        self.searched_dirs = candidates

        records = tuple(_read_candidate(path) for path in candidates)
        complete = next((record for record in records if record.is_complete), None)
        if complete is not None:
            self._record_diagnostics(complete)
            return DeviceIdentity(
                device_id=_normalize_mac(complete.device_id),
                client_id=complete.client_id,
                serial_number=complete.serial_number,
                hmac_key=complete.hmac_key,
                generation=1,
                source="legacy_config",
            )

        device_id = _first_text(record.device_id for record in records) or _physical_mac_address()
        if not device_id:
            return None

        normalized_device_id = _normalize_mac(device_id)
        client_id = _first_text(record.client_id for record in records)
        serial_number = _first_text(record.serial_number for record in records)
        hmac_key = _first_text(record.hmac_key for record in records)

        identity = create_machine_identity(
            generation=1,
            device_id=normalized_device_id,
            client_id=client_id or None,
            serial_number=serial_number or None,
            hmac_key=hmac_key or None,
        )
        contributing = next((record for record in records if record.has_any_value), None)
        if contributing is not None:
            self._record_diagnostics(contributing)
        self.recovered_client_id = bool(client_id)
        source = "machine_fingerprint_with_legacy_client" if client_id else "machine_fingerprint"
        return DeviceIdentity(
            device_id=identity.device_id,
            client_id=identity.client_id,
            serial_number=identity.serial_number,
            hmac_key=identity.hmac_key,
            generation=identity.generation,
            source=source,
        )

    def _record_diagnostics(self, record: "_CandidateRecord") -> None:
        self.imported_from = record.config_dir
        self.local_activation_marked = record.local_activation_marked
        self.recovered_client_id = bool(record.client_id)


@dataclass(frozen=True, slots=True)
class _CandidateRecord:
    config_dir: Path
    device_id: str = ""
    client_id: str = ""
    serial_number: str = ""
    hmac_key: str = ""
    local_activation_marked: bool | None = None

    @property
    def is_complete(self) -> bool:
        return all((self.device_id, self.client_id, self.serial_number, self.hmac_key))

    @property
    def has_any_value(self) -> bool:
        return any((self.device_id, self.client_id, self.serial_number, self.hmac_key))


def create_machine_identity(
    *,
    generation: int,
    device_id: str | None = None,
    client_id: str | None = None,
    serial_number: str | None = None,
    hmac_key: str | None = None,
) -> DeviceIdentity | None:
    """Create a stable PC identity compatible with the former client's fingerprint rules."""

    normalized_device_id = _normalize_mac(device_id or "") if device_id else _physical_mac_address()
    if not normalized_device_id:
        return None

    clean_mac = normalized_device_id.replace(":", "")
    resolved_serial = serial_number or (
        f"SN-{hashlib.md5(clean_mac.encode()).hexdigest()[:8].upper()}-{clean_mac}"
    )
    resolved_hmac = hmac_key or _machine_hmac_key(normalized_device_id)
    resolved_client = client_id or str(uuid.uuid4())
    return DeviceIdentity(
        device_id=normalized_device_id,
        client_id=resolved_client,
        serial_number=resolved_serial,
        hmac_key=resolved_hmac,
        generation=generation,
        source="machine_fingerprint",
    )


def _candidate_config_dirs(*, local_base: Path) -> tuple[Path, ...]:
    app_data = os.environ.get("APPDATA", "").strip()
    roaming_base = Path(app_data).expanduser() if app_data else Path.home() / "AppData" / "Roaming"
    roots = [local_base, roaming_base]
    explicit = os.environ.get("NOTE_ASSISTANT_LEGACY_CONFIG_DIR", "").strip()

    home = Path.home()
    roots.extend(
        [
            home / ".local" / "share",
            home / ".config",
            home / "Library" / "Application Support",
        ]
    )

    workspace = Path.cwd().resolve()
    workspace_roots = (workspace, *tuple(workspace.parents)[:3])
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    for root in roots:
        for app_name in LEGACY_APP_DIR_NAMES:
            candidates.append(root / app_name / app_name / "config")
            candidates.append(root / app_name / app_name)
            candidates.append(root / app_name / "config")
            candidates.append(root / app_name)
    for root in workspace_roots:
        for app_name in LEGACY_APP_DIR_NAMES:
            candidates.append(root / app_name / "config")
            candidates.append(root / app_name)
    return _deduplicate_paths(candidates)


def _read_candidate(config_dir: Path) -> _CandidateRecord:
    efuse = _read_object(config_dir / "efuse.json") or {}
    config = _read_object(config_dir / "config.json") or {}
    system_options = config.get("SYSTEM_OPTIONS")
    if not isinstance(system_options, dict):
        system_options = {}

    device_id = _clean_text(system_options.get("DEVICE_ID")) or _clean_text(
        efuse.get("mac_address")
    )
    return _CandidateRecord(
        config_dir=config_dir,
        device_id=device_id,
        client_id=_clean_text(system_options.get("CLIENT_ID")),
        serial_number=_clean_text(efuse.get("serial_number")),
        hmac_key=_clean_text(efuse.get("hmac_key")),
        local_activation_marked=(
            bool(efuse.get("activation_status")) if "activation_status" in efuse else None
        ),
    )


def _read_object(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _machine_hmac_key(mac_address: str) -> str:
    identifiers = [platform.node(), mac_address]
    machine_id = _windows_machine_guid()
    if machine_id:
        identifiers.append(machine_id)
    clean_identifiers = [value for value in identifiers if value]
    if not clean_identifiers:
        clean_identifiers.append(platform.system())
    return hashlib.sha256("||".join(clean_identifiers).encode()).hexdigest()


def _windows_machine_guid() -> str | None:
    if os.name != "nt":
        return None
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0),
        ) as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
    except (OSError, ImportError):
        return None
    return str(value).strip() or None


def _physical_mac_address() -> str | None:
    node = uuid.getnode()
    first_octet = (node >> 40) & 0xFF
    if first_octet & 0x01:
        return None
    compact = f"{node:012x}"
    if compact == "000000000000":
        return None
    return ":".join(compact[index : index + 2] for index in range(0, 12, 2))


def _first_text(values) -> str:
    return next((value for value in values if value), "")


def _clean_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _normalize_mac(value: str) -> str:
    compact = "".join(character for character in value if character.isalnum()).lower()
    if len(compact) != 12:
        return value.strip().lower()
    return ":".join(compact[index : index + 2] for index in range(0, 12, 2))


def _deduplicate_paths(paths) -> tuple[Path, ...]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        normalized = Path(path).expanduser()
        key = os.path.normcase(str(normalized.resolve(strict=False)))
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return tuple(result)
