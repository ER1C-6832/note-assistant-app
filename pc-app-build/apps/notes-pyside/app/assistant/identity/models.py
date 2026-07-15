"""Stable device identity models for Xiaozhi activation and transport headers."""

from __future__ import annotations

from dataclasses import dataclass

from ..runtime_config import IdentityRecord


@dataclass(frozen=True, slots=True)
class DeviceIdentity:
    device_id: str
    client_id: str
    serial_number: str
    hmac_key: str
    generation: int

    @classmethod
    def from_record(cls, record: IdentityRecord) -> "DeviceIdentity":
        return cls(
            device_id=record.device_id,
            client_id=record.client_id,
            serial_number=record.serial_number,
            hmac_key=record.hmac_key,
            generation=record.generation,
        )

    def to_record(self) -> IdentityRecord:
        return IdentityRecord(
            device_id=self.device_id,
            client_id=self.client_id,
            serial_number=self.serial_number,
            hmac_key=self.hmac_key,
            generation=self.generation,
        )

    @property
    def device_id_masked(self) -> str:
        return mask_identifier(self.device_id)

    @property
    def client_id_masked(self) -> str:
        return mask_identifier(self.client_id)


def mask_identifier(value: str, *, visible_prefix: int = 4, visible_suffix: int = 4) -> str:
    clean = value.strip()
    if len(clean) <= visible_prefix + visible_suffix:
        return "*" * len(clean)
    return f"{clean[:visible_prefix]}***{clean[-visible_suffix:]}"
