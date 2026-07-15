"""Versioned, device-local Assistant Runtime configuration storage."""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Callable, TypeVar

RUNTIME_CONFIG_SCHEMA_VERSION = 1


class RuntimeConfigError(ValueError):
    """Raised when the persisted runtime configuration is invalid."""


@dataclass(frozen=True, slots=True)
class IdentityRecord:
    device_id: str
    client_id: str
    serial_number: str
    hmac_key: str
    generation: int = 1


@dataclass(frozen=True, slots=True)
class RealRuntimeConfig:
    ota_url: str = ""
    authorization_url: str = ""
    activation_version: str = "v2"
    websocket_url: str = ""
    websocket_token: str = ""
    activated: bool = False
    activation_code: str = ""
    activation_challenge: str = ""
    activation_message: str = ""
    last_ota_json_redacted: str = ""


@dataclass(frozen=True, slots=True)
class FakeRuntimeConfig:
    websocket_url: str = ""
    websocket_token: str = ""
    activated: bool = False
    last_activation_json_redacted: str = ""


@dataclass(frozen=True, slots=True)
class AssistantRuntimeConfig:
    schema_version: int = RUNTIME_CONFIG_SCHEMA_VERSION
    identity: IdentityRecord | None = None
    real: RealRuntimeConfig = field(default_factory=RealRuntimeConfig)
    fake: FakeRuntimeConfig = field(default_factory=FakeRuntimeConfig)


ConfigMutator = Callable[[AssistantRuntimeConfig], AssistantRuntimeConfig]
T = TypeVar("T")


class RuntimeConfigStore:
    """Read and atomically replace one versioned JSON configuration file."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = threading.RLock()

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> AssistantRuntimeConfig:
        with self._lock:
            return self._load_unlocked()

    def save(self, config: AssistantRuntimeConfig) -> None:
        with self._lock:
            self._save_unlocked(config)

    def update(self, mutator: ConfigMutator) -> AssistantRuntimeConfig:
        with self._lock:
            current = self._load_unlocked()
            updated = mutator(current)
            self._save_unlocked(updated)
            return updated

    def update_real_endpoints(
        self,
        *,
        ota_url: str,
        authorization_url: str,
        activation_version: str = "v2",
    ) -> AssistantRuntimeConfig:
        clean_ota = ota_url.strip()
        clean_authorization = authorization_url.strip()
        clean_version = activation_version.strip() or "v2"

        def mutate(current: AssistantRuntimeConfig) -> AssistantRuntimeConfig:
            return replace(
                current,
                real=replace(
                    current.real,
                    ota_url=clean_ota,
                    authorization_url=clean_authorization,
                    activation_version=clean_version,
                ),
            )

        return self.update(mutate)

    def _load_unlocked(self) -> AssistantRuntimeConfig:
        if not self._path.exists():
            return AssistantRuntimeConfig()
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeConfigError(f"无法读取 Assistant Runtime 配置：{exc}") from exc
        return _decode_config(payload)

    def _save_unlocked(self, config: AssistantRuntimeConfig) -> None:
        _validate_config(config)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._path.with_name(f".{self._path.name}.tmp")
        encoded = json.dumps(
            asdict(config),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        try:
            temp_path.write_text(f"{encoded}\n", encoding="utf-8")
            _best_effort_private_permissions(temp_path)
            os.replace(temp_path, self._path)
            _best_effort_private_permissions(self._path)
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)


def _decode_config(payload: object) -> AssistantRuntimeConfig:
    if not isinstance(payload, dict):
        raise RuntimeConfigError("Assistant Runtime 配置根节点必须是对象")
    schema_version = payload.get("schema_version")
    if schema_version != RUNTIME_CONFIG_SCHEMA_VERSION:
        raise RuntimeConfigError(f"不支持的 Assistant Runtime 配置版本：{schema_version!r}")

    identity_payload = payload.get("identity")
    identity = None
    if identity_payload is not None:
        if not isinstance(identity_payload, dict):
            raise RuntimeConfigError("identity 必须是对象或 null")
        try:
            identity = IdentityRecord(
                device_id=str(identity_payload["device_id"]),
                client_id=str(identity_payload["client_id"]),
                serial_number=str(identity_payload["serial_number"]),
                hmac_key=str(identity_payload["hmac_key"]),
                generation=int(identity_payload.get("generation", 1)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeConfigError("identity 字段不完整") from exc

    real = _decode_dataclass(RealRuntimeConfig, payload.get("real"), "real")
    fake = _decode_dataclass(FakeRuntimeConfig, payload.get("fake"), "fake")
    config = AssistantRuntimeConfig(
        schema_version=RUNTIME_CONFIG_SCHEMA_VERSION,
        identity=identity,
        real=real,
        fake=fake,
    )
    _validate_config(config)
    return config


def _decode_dataclass(model: type[T], payload: object, name: str) -> T:
    if payload is None:
        return model()  # type: ignore[call-arg]
    if not isinstance(payload, dict):
        raise RuntimeConfigError(f"{name} 必须是对象")
    try:
        return model(**payload)  # type: ignore[arg-type]
    except TypeError as exc:
        raise RuntimeConfigError(f"{name} 字段不兼容") from exc


def _validate_config(config: AssistantRuntimeConfig) -> None:
    if config.schema_version != RUNTIME_CONFIG_SCHEMA_VERSION:
        raise RuntimeConfigError(f"不支持的 schema_version：{config.schema_version}")
    identity = config.identity
    if identity is not None:
        if identity.generation < 1:
            raise RuntimeConfigError("identity generation 必须大于 0")
        for name, value in (
            ("device_id", identity.device_id),
            ("client_id", identity.client_id),
            ("serial_number", identity.serial_number),
            ("hmac_key", identity.hmac_key),
        ):
            if not value.strip():
                raise RuntimeConfigError(f"identity.{name} 不能为空")


def clear_identity_bound_runtime(
    config: AssistantRuntimeConfig,
) -> AssistantRuntimeConfig:
    """Clear credentials tied to the previous identity while preserving endpoint settings."""

    return replace(
        config,
        real=RealRuntimeConfig(
            ota_url=config.real.ota_url,
            authorization_url=config.real.authorization_url,
            activation_version=config.real.activation_version,
        ),
        fake=FakeRuntimeConfig(),
    )


def _best_effort_private_permissions(path: Path) -> None:
    try:
        path.chmod(0o600)
    except OSError:
        # Windows ACLs are not fully represented by chmod. Packaging can harden this later.
        return
