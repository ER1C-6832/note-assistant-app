"""Generate, persist, mask, migrate, and reset the device-local Assistant identity."""

from __future__ import annotations

import asyncio
import secrets
import uuid
from collections.abc import Callable
from dataclasses import replace

from .legacy import create_machine_identity
from .models import DeviceIdentity
from .store import DeviceIdentityStore

IdentityMigration = Callable[[], DeviceIdentity | None]
_TRUST_PRIORITY = {
    "unknown": 0,
    "generated_random": 1,
    "machine_fingerprint": 2,
    "machine_fingerprint_with_legacy_client": 3,
    "legacy_config": 4,
    "explicit_reset": 5,
}


class DeviceIdentityManager:
    def __init__(
        self,
        store: DeviceIdentityStore,
        *,
        legacy_identity: IdentityMigration | None = None,
    ) -> None:
        self._store = store
        self._legacy_identity = legacy_identity
        self.last_identity_replaced = False

    async def ensure_identity(self) -> DeviceIdentity:
        existing = await asyncio.to_thread(self._store.load)
        candidate = await self._migration_candidate(existing)

        if existing is not None:
            if candidate is not None and _should_replace(existing, candidate):
                replacement = _merge_candidate_with_existing(candidate, existing)
                self.last_identity_replaced = True
                return await asyncio.to_thread(self._store.install_migrated, replacement)
            return existing

        if candidate is not None:
            return await asyncio.to_thread(self._store.save, candidate)

        machine_identity = create_machine_identity(generation=1)
        if machine_identity is not None:
            return await asyncio.to_thread(self._store.save, machine_identity)

        return await asyncio.to_thread(self._store.ensure, self._generate_random)

    async def reset_identity(self) -> DeviceIdentity:
        self.last_identity_replaced = True
        return await asyncio.to_thread(self._store.reset, self._generate_reset)

    async def _migration_candidate(
        self,
        existing: DeviceIdentity | None,
    ) -> DeviceIdentity | None:
        migrated = None
        if self._legacy_identity is not None:
            migrated = await asyncio.to_thread(self._legacy_identity)
        if migrated is not None:
            return migrated

        client_id = existing.client_id if existing is not None else None
        return create_machine_identity(generation=1, client_id=client_id)

    @staticmethod
    def _generate_random(generation: int) -> DeviceIdentity:
        mac = bytearray(secrets.token_bytes(6))
        mac[0] = (mac[0] | 0x02) & 0xFE
        device_id = ":".join(f"{part:02x}" for part in mac)
        return DeviceIdentity(
            device_id=device_id,
            client_id=str(uuid.uuid4()),
            serial_number=uuid.uuid4().hex.upper(),
            hmac_key=secrets.token_hex(32),
            generation=generation,
            source="generated_random",
        )

    @staticmethod
    def _generate_reset(generation: int) -> DeviceIdentity:
        return replace(
            DeviceIdentityManager._generate_random(generation),
            source="explicit_reset",
        )


def _should_replace(existing: DeviceIdentity, candidate: DeviceIdentity) -> bool:
    existing_priority = _TRUST_PRIORITY.get(existing.source, 0)
    candidate_priority = _TRUST_PRIORITY.get(candidate.source, 0)
    if candidate_priority <= existing_priority:
        return False
    return (
        existing.device_id != candidate.device_id
        or existing.source != candidate.source
        or candidate.source in {"legacy_config", "machine_fingerprint_with_legacy_client"}
    )


def _merge_candidate_with_existing(
    candidate: DeviceIdentity,
    existing: DeviceIdentity,
) -> DeviceIdentity:
    if candidate.source != "machine_fingerprint":
        return candidate
    return replace(candidate, client_id=existing.client_id)
