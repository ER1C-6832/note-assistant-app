"""Windows-first PortAudio device registry with private stable fingerprints."""

from __future__ import annotations

import hashlib
import platform
import threading
import time
from collections.abc import Callable
from typing import Any

from .gate6_contracts import (
    AudioDeviceDescriptor,
    AudioDeviceSnapshot,
    AudioPlatform,
    AudioRouteState,
    DeviceDirection,
    DevicePreference,
    DevicePreferenceMode,
    PublicAudioFormat,
    ResolvedAudioRoute,
    public_format_set,
)

PyAudioFactory = Callable[[], Any]


class AudioDeviceRegistryUnavailable(RuntimeError):
    pass


def _current_platform() -> AudioPlatform:
    value = platform.system().strip().lower()
    if value == "windows":
        return AudioPlatform.WINDOWS
    if value == "darwin":
        return AudioPlatform.MACOS
    if value == "linux":
        return AudioPlatform.LINUX
    return AudioPlatform.OTHER


def _private_fingerprint(
    *,
    platform_value: AudioPlatform,
    host_api: str,
    public_name: str,
    input_channels: int,
    output_channels: int,
    sample_rate: int,
    duplicate_ordinal: int,
) -> str:
    raw = "|".join(
        (
            platform_value.value,
            host_api.casefold().strip(),
            public_name.casefold().strip(),
            str(input_channels),
            str(output_channels),
            str(sample_rate),
            str(duplicate_ordinal),
        )
    )
    return "portaudio:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def public_device_key(opaque_device_id: str) -> str:
    """Return a transient UI key without exposing the persisted endpoint fingerprint."""

    digest = hashlib.sha256(opaque_device_id.encode("utf-8")).hexdigest()[:16]
    return f"device:{digest}"


class PyAudioDeviceRegistry:
    """Enumerate, resolve and privately map PortAudio devices.

    PortAudio indexes are retained only in the current snapshot map. Persisted
    preferences use a private device fingerprint and never expose the index to QML.
    """

    def __init__(self, *, pyaudio_factory: PyAudioFactory | None = None) -> None:
        self._factory = pyaudio_factory
        self._lock = threading.RLock()
        self._snapshot_generation = 0
        self._route_generation = 0
        self._last_snapshot_signature: tuple[object, ...] | None = None
        self._last_route_signature: tuple[object, ...] | None = None
        self._snapshot: AudioDeviceSnapshot | None = None
        self._index_by_id: dict[str, int] = {}

    def snapshot(self) -> AudioDeviceSnapshot:
        try:
            manager = self._create_manager()
        except Exception as exc:
            return self._unavailable_snapshot(exc)
        try:
            devices, index_by_id = self._enumerate(manager)
        except Exception as exc:
            return self._unavailable_snapshot(exc)
        finally:
            manager.terminate()

        signature = tuple(
            (
                item.opaque_device_id,
                item.default_input,
                item.default_output,
                item.available,
                tuple(tuple(value.public_dict().values()) for value in item.supported_formats),
            )
            for item in devices
        )
        with self._lock:
            if self._last_snapshot_signature != signature:
                self._snapshot_generation += 1
                self._last_snapshot_signature = signature
            snapshot = AudioDeviceSnapshot(
                self._snapshot_generation,
                devices,
                captured_at_ns=time.perf_counter_ns(),
            )
            self._snapshot = snapshot
            self._index_by_id = index_by_id
            return snapshot

    def _unavailable_snapshot(self, exc: Exception) -> AudioDeviceSnapshot:
        signature = ("unavailable", type(exc).__name__)
        with self._lock:
            if self._last_snapshot_signature != signature:
                self._snapshot_generation += 1
                self._last_snapshot_signature = signature
            snapshot = AudioDeviceSnapshot(
                self._snapshot_generation,
                (),
                captured_at_ns=time.perf_counter_ns(),
                error_code=f"device_enumeration_failed:{type(exc).__name__}",
            )
            self._snapshot = snapshot
            self._index_by_id = {}
            return snapshot

    def resolve(
        self,
        input_preference: DevicePreference,
        output_preference: DevicePreference,
    ) -> ResolvedAudioRoute:
        if input_preference.direction is not DeviceDirection.INPUT:
            raise ValueError("input preference has the wrong direction")
        if output_preference.direction is not DeviceDirection.OUTPUT:
            raise ValueError("output preference has the wrong direction")
        snapshot = self.snapshot()
        input_device, input_fallback = self._resolve_direction(snapshot.devices, input_preference)
        output_device, output_fallback = self._resolve_direction(
            snapshot.devices, output_preference
        )
        error_code = snapshot.error_code
        state = AudioRouteState.READY
        if input_device is None or output_device is None:
            state = AudioRouteState.UNAVAILABLE
            error_code = error_code or (
                "input_device_unavailable" if input_device is None else "output_device_unavailable"
            )
        elif input_fallback or output_fallback:
            error_code = "pinned_device_temporarily_unavailable"
        signature = (
            input_device.opaque_device_id if input_device else None,
            output_device.opaque_device_id if output_device else None,
            input_fallback,
            output_fallback,
            state.value,
        )
        with self._lock:
            if self._last_route_signature != signature:
                self._route_generation += 1
                self._last_route_signature = signature
            generation = self._route_generation
        return ResolvedAudioRoute(
            route_generation=generation,
            input_device=input_device,
            output_device=output_device,
            input_preference=input_preference,
            output_preference=output_preference,
            state=state,
            temporary_input_fallback=input_fallback,
            temporary_output_fallback=output_fallback,
            error_code=error_code,
        )

    def device_index(self, opaque_device_id: str, direction: DeviceDirection) -> int:
        with self._lock:
            snapshot = self._snapshot
            index = self._index_by_id.get(opaque_device_id)
        if snapshot is None or index is None:
            self.snapshot()
            with self._lock:
                snapshot = self._snapshot
                index = self._index_by_id.get(opaque_device_id)
        if snapshot is None or index is None:
            raise AudioDeviceRegistryUnavailable("selected device is not in the current snapshot")
        descriptor = next(
            (item for item in snapshot.devices if item.opaque_device_id == opaque_device_id),
            None,
        )
        if descriptor is None or not descriptor.available:
            raise AudioDeviceRegistryUnavailable("selected device is unavailable")
        if direction is DeviceDirection.INPUT and not descriptor.can_input:
            raise AudioDeviceRegistryUnavailable("selected device cannot capture")
        if direction is DeviceDirection.OUTPUT and not descriptor.can_output:
            raise AudioDeviceRegistryUnavailable("selected device cannot render")
        return index

    def opaque_id_for_public_key(self, key: str, direction: DeviceDirection) -> str | None:
        with self._lock:
            snapshot = self._snapshot
        if snapshot is None:
            snapshot = self.snapshot()
        for item in snapshot.devices:
            supported = item.can_input if direction is DeviceDirection.INPUT else item.can_output
            if supported and public_device_key(item.opaque_device_id) == key:
                return item.opaque_device_id
        return None

    def _create_manager(self) -> Any:
        if self._factory is not None:
            return self._factory()
        try:
            import pyaudio
        except ImportError as exc:
            raise AudioDeviceRegistryUnavailable("pyaudio is not installed") from exc
        return pyaudio.PyAudio()

    def _enumerate(self, manager: Any) -> tuple[tuple[AudioDeviceDescriptor, ...], dict[str, int]]:
        platform_value = _current_platform()
        default_input = self._default_index(manager, input_direction=True)
        default_output = self._default_index(manager, input_direction=False)
        duplicates: dict[tuple[object, ...], int] = {}
        descriptors: list[AudioDeviceDescriptor] = []
        indexes: dict[str, int] = {}
        for index in range(int(manager.get_device_count())):
            info = manager.get_device_info_by_index(index)
            input_channels = max(0, int(info.get("maxInputChannels", 0) or 0))
            output_channels = max(0, int(info.get("maxOutputChannels", 0) or 0))
            if input_channels == 0 and output_channels == 0:
                continue
            public_name = str(info.get("name") or f"Audio device {index}")[:120]
            host_api_index = int(info.get("hostApi", 0) or 0)
            try:
                host_info = manager.get_host_api_info_by_index(host_api_index)
                host_api = str(host_info.get("name") or f"Host API {host_api_index}")[:80]
            except Exception:
                host_api = f"Host API {host_api_index}"
            sample_rate = max(1, round(float(info.get("defaultSampleRate", 16_000))))
            duplicate_key = (
                host_api.casefold(),
                public_name.casefold(),
                input_channels,
                output_channels,
                sample_rate,
            )
            ordinal = duplicates.get(duplicate_key, 0)
            duplicates[duplicate_key] = ordinal + 1
            opaque_id = _private_fingerprint(
                platform_value=platform_value,
                host_api=host_api,
                public_name=public_name,
                input_channels=input_channels,
                output_channels=output_channels,
                sample_rate=sample_rate,
                duplicate_ordinal=ordinal,
            )
            formats = self._supported_formats(
                manager,
                index=index,
                input_channels=input_channels,
                output_channels=output_channels,
            )
            descriptors.append(
                AudioDeviceDescriptor(
                    opaque_device_id=opaque_id,
                    public_name=public_name,
                    platform=platform_value,
                    host_api=host_api,
                    can_input=input_channels > 0,
                    can_output=output_channels > 0,
                    default_input=index == default_input,
                    default_output=index == default_output,
                    supported_formats=formats,
                    reported_input_latency_ms=(
                        round(float(info.get("defaultLowInputLatency", 0.0)) * 1000, 3)
                        if input_channels
                        else None
                    ),
                    reported_output_latency_ms=(
                        round(float(info.get("defaultLowOutputLatency", 0.0)) * 1000, 3)
                        if output_channels
                        else None
                    ),
                )
            )
            indexes[opaque_id] = index
        return tuple(descriptors), indexes

    @staticmethod
    def _default_index(manager: Any, *, input_direction: bool) -> int | None:
        try:
            info = (
                manager.get_default_input_device_info()
                if input_direction
                else manager.get_default_output_device_info()
            )
            return int(info["index"])
        except Exception:
            return None

    @staticmethod
    def _supported_formats(
        manager: Any,
        *,
        index: int,
        input_channels: int,
        output_channels: int,
    ) -> tuple[PublicAudioFormat, ...]:
        try:
            import pyaudio

            int16 = pyaudio.paInt16
        except ImportError:
            int16 = 8
        candidates: list[PublicAudioFormat] = []
        probes = (
            (16_000, 1, DeviceDirection.INPUT),
            (16_000, 1, DeviceDirection.OUTPUT),
            (24_000, 1, DeviceDirection.OUTPUT),
            (48_000, 1, DeviceDirection.OUTPUT),
            (48_000, 2, DeviceDirection.OUTPUT),
        )
        for rate, channels, direction in probes:
            if direction is DeviceDirection.INPUT and input_channels < channels:
                continue
            if direction is DeviceDirection.OUTPUT and output_channels < channels:
                continue
            kwargs: dict[str, object] = {}
            if direction is DeviceDirection.INPUT:
                kwargs.update(
                    input_device=index,
                    input_channels=channels,
                    input_format=int16,
                )
            else:
                kwargs.update(
                    output_device=index,
                    output_channels=channels,
                    output_format=int16,
                )
            try:
                supported = manager.is_format_supported(rate, **kwargs)
            except (OSError, ValueError):
                supported = False
            if supported:
                candidates.append(PublicAudioFormat(rate, channels, 2, 20))
        return public_format_set(candidates)

    @staticmethod
    def _resolve_direction(
        devices: tuple[AudioDeviceDescriptor, ...], preference: DevicePreference
    ) -> tuple[AudioDeviceDescriptor | None, bool]:
        supports = (
            (lambda item: item.can_input)
            if preference.direction is DeviceDirection.INPUT
            else (lambda item: item.can_output)
        )
        default_flag = (
            (lambda item: item.default_input)
            if preference.direction is DeviceDirection.INPUT
            else (lambda item: item.default_output)
        )
        available = tuple(item for item in devices if item.available and supports(item))
        default = next((item for item in available if default_flag(item)), None)
        if preference.mode is DevicePreferenceMode.FOLLOW_SYSTEM_DEFAULT:
            return default, False
        pinned = next(
            (item for item in available if item.opaque_device_id == preference.pinned_device_id),
            None,
        )
        if pinned is not None:
            return pinned, False
        if preference.allow_temporary_default_fallback:
            return default, default is not None
        return None, False
