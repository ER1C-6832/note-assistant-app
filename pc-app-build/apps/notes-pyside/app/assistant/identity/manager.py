"""Generate, persist, mask, migrate, and reset the device-local Assistant identity."""

from __future__ import annotations

import asyncio
import secrets
import uuid
from collections.abc import Callable

from .models import DeviceIdentity
from .store import DeviceIdentityStore

IdentityMigration = Callable[[], DeviceIdentity | None]


class DeviceIdentityManager:
    def __init__(
        self,
        store: DeviceIdentityStore,
        *,
        legacy_identity: IdentityMigration | None = None,
    ) -> None:
        self._store = store
        self._legacy_identity = legacy_identity

    async def ensure_identity(self) -> DeviceIdentity:
        existing = await asyncio.to_thread(self._store.load)
        if existing is not None:
            return existing

        if self._legacy_identity is not None:
            migrated = await asyncio.to_thread(self._legacy_identity)
            if migrated is not None:
                return await asyncio.to_thread(self._store.save, migrated)

        return await asyncio.to_thread(self._store.ensure, self._generate)

    async def reset_identity(self) -> DeviceIdentity:
        return await asyncio.to_thread(self._store.reset, self._generate)

    @staticmethod
    def _generate(generation: int) -> DeviceIdentity:
        mac = bytearray(secrets.token_bytes(6))
        mac[0] = (mac[0] | 0x02) & 0xFE
        device_id = ":".join(f"{part:02x}" for part in mac)
        return DeviceIdentity(
            device_id=device_id,
            client_id=str(uuid.uuid4()),
            serial_number=uuid.uuid4().hex.upper(),
            hmac_key=secrets.token_hex(32),
            generation=generation,
        )
