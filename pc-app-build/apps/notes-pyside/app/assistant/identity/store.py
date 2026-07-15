"""Identity persistence built on the versioned RuntimeConfigStore."""

from __future__ import annotations

from dataclasses import replace

from ..runtime_config import (
    AssistantRuntimeConfig,
    RuntimeConfigStore,
    clear_identity_bound_runtime,
)
from .models import DeviceIdentity


class DeviceIdentityStore:
    def __init__(self, config_store: RuntimeConfigStore) -> None:
        self._config_store = config_store

    def load(self) -> DeviceIdentity | None:
        record = self._config_store.load().identity
        return DeviceIdentity.from_record(record) if record is not None else None

    def save(self, identity: DeviceIdentity) -> DeviceIdentity:
        self._config_store.update(lambda current: replace(current, identity=identity.to_record()))
        return identity

    def install_migrated(self, identity: DeviceIdentity) -> DeviceIdentity:
        result: DeviceIdentity | None = None

        def mutate(current: AssistantRuntimeConfig) -> AssistantRuntimeConfig:
            nonlocal result
            previous_generation = current.identity.generation if current.identity is not None else 0
            result = replace(identity, generation=max(identity.generation, previous_generation + 1))
            cleared = clear_identity_bound_runtime(current)
            return replace(cleared, identity=result.to_record())

        self._config_store.update(mutate)
        assert result is not None
        return result

    def ensure(self, factory) -> DeviceIdentity:
        result: DeviceIdentity | None = None

        def mutate(current: AssistantRuntimeConfig) -> AssistantRuntimeConfig:
            nonlocal result
            if current.identity is not None:
                result = DeviceIdentity.from_record(current.identity)
                return current
            result = factory(1)
            return replace(current, identity=result.to_record())

        self._config_store.update(mutate)
        assert result is not None
        return result

    def reset(self, factory) -> DeviceIdentity:
        result: DeviceIdentity | None = None

        def mutate(current: AssistantRuntimeConfig) -> AssistantRuntimeConfig:
            nonlocal result
            previous_generation = current.identity.generation if current.identity is not None else 0
            result = factory(previous_generation + 1)
            cleared = clear_identity_bound_runtime(current)
            return replace(cleared, identity=result.to_record())

        self._config_store.update(mutate)
        assert result is not None
        return result
