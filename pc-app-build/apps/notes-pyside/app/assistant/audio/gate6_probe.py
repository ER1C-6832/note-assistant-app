"""Gate 6.0 probe contracts, bounded resources, fakes, and report privacy.

This module is used only by isolated probes and tests.  It does not alter the
current Gate 3/4 product capture or playback topology.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import platform
import re
import sys
import threading
import time
from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, TypeVar

from .gate6_contracts import (
    AudioDeviceDescriptor,
    AudioDeviceSnapshot,
    AudioPlatform,
    AudioProcessingMetrics,
    AudioRouteState,
    CaptureActivity,
    KeywordSpotResult,
    MicrophoneOwner,
    PlaybackActivity,
    ProcessingState,
    PublicAudioFormat,
    state_projection,
)

PROBE_SCHEMA_VERSION = 1
PROBE_RENDER_QUEUE_CAPACITY = 64
PROBE_CAPTURE_QUEUE_CAPACITY = 64
PROBE_EVENT_CAPACITY = 128
PROBE_INTERNAL_BLOCK_MS = 10
PROBE_PUBLIC_FRAME_MS = 20
PROBE_WATCHDOG_MS = 2_000
PROBE_MAX_JSON_BYTES = 64 * 1024
PROBE_MAX_PUBLIC_DEVICES = 64
PROBE_KWS_COOLDOWN_MS = 1_500

_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)((?:token|password|api[_-]?key|secret)\s*[:=]\s*)[^\s,;]+"),
)
_GUID_PATTERN = re.compile(
    r"(?i)(?:\{)?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?:\})?"
)
_PRIVATE_KEY_FRAGMENTS = (
    "pcm",
    "opus",
    "reference_bytes",
    "raw_audio",
    "native_handle",
    "endpoint_guid",
    "endpoint_uid",
    "model_tensor",
    "authorization",
    "password",
    "secret",
    "token",
)

T = TypeVar("T")


class ProbeStatus(str, Enum):
    COMPLETE = "probe_complete"
    BLOCKED = "probe_blocked"
    FAILED = "probe_failed"
    PENDING_REAL = "pending_real_evidence"


class ProbeBackendKind(str, Enum):
    WEBRTC_APM = "webrtc_apm"
    WINDOWS_SYSTEM_AEC = "windows_system_aec"
    MACOS_VOICE_PROCESSING = "macos_voice_processing"
    BYPASS = "bypass"


class ProbeScenario(str, Enum):
    DEVICE_INVENTORY = "device_inventory"
    DUPLEX = "duplex"
    AEC_CAPABILITY = "aec_capability"
    AEC_FAR_END_ONLY = "aec_far_end_only"
    AEC_DOUBLE_TALK = "aec_double_talk"
    KWS_IMPORT = "kws_import"
    KWS_LIVE = "kws_live"
    FAKE_CONTRACT = "fake_contract"


class ProbeQueueOverflow(RuntimeError):
    pass


class BoundedProbeQueue(Generic[T]):
    """Thread-safe fail-on-overflow queue used by isolated probe callbacks."""

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("queue capacity must be positive")
        self._capacity = int(capacity)
        self._items: deque[T] = deque()
        self._peak = 0
        self._overflow_count = 0
        self._closed = False
        self._condition = threading.Condition()

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def peak(self) -> int:
        with self._condition:
            return self._peak

    @property
    def overflow_count(self) -> int:
        with self._condition:
            return self._overflow_count

    @property
    def closed(self) -> bool:
        with self._condition:
            return self._closed

    def __len__(self) -> int:
        with self._condition:
            return len(self._items)

    def put(self, item: T) -> None:
        with self._condition:
            if self._closed:
                raise RuntimeError("probe queue is closed")
            if len(self._items) >= self._capacity:
                self._overflow_count += 1
                raise ProbeQueueOverflow("bounded probe queue overflow")
            self._items.append(item)
            self._peak = max(self._peak, len(self._items))
            self._condition.notify()

    def get(self, timeout: float | None = None) -> T:
        deadline = None if timeout is None else time.monotonic() + max(0.0, timeout)
        with self._condition:
            while not self._items:
                if self._closed:
                    raise RuntimeError("probe queue is closed")
                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("probe queue get timed out")
                    self._condition.wait(remaining)
                else:
                    self._condition.wait()
            return self._items.popleft()

    def drain(self) -> tuple[T, ...]:
        with self._condition:
            values = tuple(self._items)
            self._items.clear()
            return values

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._items.clear()
            self._condition.notify_all()


@dataclass(slots=True)
class ProbeResourceTracker:
    """Track actual probe-owned resources instead of relying on state booleans."""

    capture_streams: int = 0
    output_streams: int = 0
    duplex_sessions: int = 0
    processing_workers: int = 0
    kws_workers: int = 0
    route_observers: int = 0
    worker_threads: set[str] = field(default_factory=set)
    microphone_owner: MicrophoneOwner = MicrophoneOwner.NONE
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def increment(self, name: str) -> None:
        with self._lock:
            current = getattr(self, name)
            if not isinstance(current, int):
                raise TypeError(f"resource {name} is not an integer counter")
            setattr(self, name, current + 1)

    def decrement(self, name: str) -> None:
        with self._lock:
            current = getattr(self, name)
            if not isinstance(current, int) or current <= 0:
                raise RuntimeError(f"resource {name} underflow")
            setattr(self, name, current - 1)

    def add_thread(self, name: str) -> None:
        with self._lock:
            self.worker_threads.add(str(name))

    def remove_thread(self, name: str) -> None:
        with self._lock:
            self.worker_threads.discard(str(name))

    def set_owner(self, owner: MicrophoneOwner) -> None:
        with self._lock:
            if (
                owner is not MicrophoneOwner.NONE
                and self.microphone_owner is not MicrophoneOwner.NONE
            ):
                raise RuntimeError("a second microphone owner is not allowed")
            self.microphone_owner = owner

    def release_owner(self, owner: MicrophoneOwner) -> None:
        with self._lock:
            if self.microphone_owner not in {owner, MicrophoneOwner.NONE}:
                raise RuntimeError("stale microphone owner cannot release the lease")
            self.microphone_owner = MicrophoneOwner.NONE

    def terminal_dict(
        self,
        *,
        render_queue: BoundedProbeQueue[object] | None = None,
        capture_queue: BoundedProbeQueue[object] | None = None,
        pending_tasks: Sequence[str] = (),
    ) -> dict[str, object]:
        with self._lock:
            return {
                "capture_stream": self.capture_streams,
                "output_stream": self.output_streams,
                "duplex_session": self.duplex_sessions,
                "render_queue_items": (len(render_queue) if render_queue is not None else 0),
                "capture_queue_items": (len(capture_queue) if capture_queue is not None else 0),
                "processing_worker": self.processing_workers,
                "kws_worker": self.kws_workers,
                "route_observer": self.route_observers,
                "worker_threads": sorted(self.worker_threads),
                "microphone_lease": self.microphone_owner.value,
                "pending_tasks": sorted(str(item) for item in pending_tasks),
                "second_python_process": 0,
            }

    def is_terminal_zero(self, **kwargs: object) -> bool:
        terminal = self.terminal_dict(**kwargs)
        return all(
            (
                terminal["capture_stream"] == 0,
                terminal["output_stream"] == 0,
                terminal["duplex_session"] == 0,
                terminal["render_queue_items"] == 0,
                terminal["capture_queue_items"] == 0,
                terminal["processing_worker"] == 0,
                terminal["kws_worker"] == 0,
                terminal["route_observer"] == 0,
                terminal["worker_threads"] == [],
                terminal["microphone_lease"] == MicrophoneOwner.NONE.value,
                terminal["pending_tasks"] == [],
                terminal["second_python_process"] == 0,
            )
        )


@dataclass(frozen=True, slots=True)
class BackendCapability:
    backend: ProbeBackendKind
    import_name: str | None
    available: bool
    current_platform_candidate: bool
    create_attempted: bool = False
    create_success: bool = False
    required_block_ms: int | None = None
    aec_advertised: bool = False
    ns_advertised: bool = False
    agc_advertised: bool = False
    error_code: str | None = None

    def public_dict(self) -> dict[str, object]:
        return {
            "backend": self.backend.value,
            "import_name": self.import_name,
            "available": self.available,
            "current_platform_candidate": self.current_platform_candidate,
            "create_attempted": self.create_attempted,
            "create_success": self.create_success,
            "required_block_ms": self.required_block_ms,
            "aec_advertised": self.aec_advertised,
            "ns_advertised": self.ns_advertised,
            "agc_advertised": self.agc_advertised,
            "error_code": self.error_code,
        }


@dataclass(frozen=True, slots=True)
class ProbeReport:
    scenario: ProbeScenario
    status: ProbeStatus
    platform_public: str
    result: Mapping[str, object]
    terminal: Mapping[str, object]
    error_code: str | None = None
    human_observation: str = "not_run"
    payload_persisted: bool = False
    secrets_redacted: bool = True
    schema_version: int = PROBE_SCHEMA_VERSION

    def public_dict(self) -> dict[str, object]:
        value = {
            "schema_version": self.schema_version,
            "scenario": self.scenario.value,
            "status": self.status.value,
            "platform": self.platform_public,
            "result": sanitize_public_value(self.result),
            "terminal": sanitize_public_value(self.terminal),
            "error_code": self.error_code,
            "human_observation": self.human_observation,
            "payload_persisted": self.payload_persisted,
            "secrets_redacted": self.secrets_redacted,
        }
        ensure_probe_report_safe(value)
        return value


class FakeKeywordSpotter:
    """Deterministic cooldown fake; it never opens a microphone or model file."""

    def __init__(self, keyword: str = "小智小智", cooldown_ms: int = PROBE_KWS_COOLDOWN_MS) -> None:
        self.keyword = keyword
        self.cooldown_ns = int(cooldown_ms) * 1_000_000
        self.generation = 0
        self.last_hit_ns: int | None = None
        self.closed = False

    def reset(self, generation: int) -> None:
        if self.closed:
            raise RuntimeError("fake KWS is closed")
        self.generation = generation
        self.last_hit_ns = None

    def accept_text(self, text: str, detected_at_ns: int) -> KeywordSpotResult | None:
        if self.closed or self.keyword not in text:
            return None
        if self.last_hit_ns is not None and detected_at_ns - self.last_hit_ns < self.cooldown_ns:
            return None
        self.last_hit_ns = detected_at_ns
        return KeywordSpotResult(self.generation, self.keyword, detected_at_ns, score=1.0)

    def close(self) -> None:
        self.closed = True


def platform_name() -> str:
    system = platform.system().strip().lower()
    return system or "unknown"


def detect_backend_capabilities() -> tuple[BackendCapability, ...]:
    current = platform_name()
    module_candidates = (
        (ProbeBackendKind.WEBRTC_APM, "aec_audio_processing"),
        (ProbeBackendKind.WEBRTC_APM, "webrtc_apm"),
        (ProbeBackendKind.WEBRTC_APM, "webrtc_audio_processing"),
        (ProbeBackendKind.WINDOWS_SYSTEM_AEC, None),
        (ProbeBackendKind.MACOS_VOICE_PROCESSING, None),
        (ProbeBackendKind.BYPASS, None),
    )
    values: list[BackendCapability] = []
    for backend, import_name in module_candidates:
        if import_name is not None:
            available = importlib.util.find_spec(import_name) is not None
            candidate = backend is ProbeBackendKind.WEBRTC_APM
            values.append(
                BackendCapability(
                    backend=backend,
                    import_name=import_name,
                    available=available,
                    current_platform_candidate=candidate,
                    required_block_ms=10,
                    aec_advertised=available,
                    ns_advertised=available,
                    agc_advertised=available,
                    error_code=None if available else "backend_import_unavailable",
                )
            )
        elif backend is ProbeBackendKind.WINDOWS_SYSTEM_AEC:
            values.append(
                BackendCapability(
                    backend=backend,
                    import_name=None,
                    available=current == "windows",
                    current_platform_candidate=current == "windows",
                    error_code=(
                        "requires_endpoint_probe"
                        if current == "windows"
                        else "platform_not_windows"
                    ),
                )
            )
        elif backend is ProbeBackendKind.MACOS_VOICE_PROCESSING:
            values.append(
                BackendCapability(
                    backend=backend,
                    import_name=None,
                    available=current == "darwin",
                    current_platform_candidate=current == "darwin",
                    error_code=(
                        "requires_voice_processing_probe"
                        if current == "darwin"
                        else "platform_not_macos"
                    ),
                )
            )
        else:
            values.append(
                BackendCapability(
                    backend=backend,
                    import_name=None,
                    available=True,
                    current_platform_candidate=True,
                    create_attempted=True,
                    create_success=True,
                    required_block_ms=PROBE_INTERNAL_BLOCK_MS,
                    error_code=None,
                )
            )
    return tuple(values)


def make_fake_device_snapshot(kind: str = "many") -> AudioDeviceSnapshot:
    audio_format = PublicAudioFormat(16_000, 1, 2, 20)
    platform_value = AudioPlatform.WINDOWS
    if kind == "empty":
        devices: tuple[AudioDeviceDescriptor, ...] = ()
    elif kind == "one":
        devices = (
            AudioDeviceDescriptor(
                "fake-default-duplex",
                "Fake Default Duplex",
                platform_value,
                "FakeHost",
                can_input=True,
                can_output=True,
                default_input=True,
                default_output=True,
                supported_formats=(audio_format,),
            ),
        )
    elif kind == "directional":
        devices = (
            AudioDeviceDescriptor(
                "fake-input",
                "Fake Input",
                platform_value,
                "FakeHost",
                can_input=True,
                can_output=False,
                default_input=True,
                supported_formats=(audio_format,),
            ),
            AudioDeviceDescriptor(
                "fake-output",
                "Fake Output",
                platform_value,
                "FakeHost",
                can_input=False,
                can_output=True,
                default_output=True,
                supported_formats=(audio_format,),
            ),
        )
    elif kind == "many":
        devices = make_fake_device_snapshot("directional").devices + (
            AudioDeviceDescriptor(
                "fake-usb-duplex",
                "Fake USB Headset",
                platform_value,
                "FakeHost",
                can_input=True,
                can_output=True,
                supported_formats=(
                    audio_format,
                    PublicAudioFormat(48_000, 2, 2, 10),
                ),
                route_class="headset",
            ),
        )
    else:
        raise ValueError("unknown fake device snapshot kind")
    return AudioDeviceSnapshot(1, devices, captured_at_ns=1_000_000)


def run_fake_probe_contract() -> ProbeReport:
    tracker = ProbeResourceTracker()
    render_queue: BoundedProbeQueue[int] = BoundedProbeQueue(2)
    capture_queue: BoundedProbeQueue[int] = BoundedProbeQueue(2)
    overflow_seen = False
    render_queue.put(1)
    render_queue.put(2)
    try:
        render_queue.put(3)
    except ProbeQueueOverflow:
        overflow_seen = True
    render_queue.drain()

    snapshots = {
        name: make_fake_device_snapshot(name) for name in ("empty", "one", "directional", "many")
    }
    ten_ms = PublicAudioFormat(16_000, 1, 2, 10)
    twenty_ms = PublicAudioFormat(16_000, 1, 2, 20)
    ordering = [100, 200, 300]
    kws = FakeKeywordSpotter(cooldown_ms=1000)
    kws.reset(7)
    first = kws.accept_text("请叫醒小智小智", 1_000_000_000)
    duplicate = kws.accept_text("小智小智", 1_100_000_000)
    later = kws.accept_text("小智小智", 2_100_000_000)
    kws.close()

    render_queue.close()
    capture_queue.close()
    terminal = tracker.terminal_dict(render_queue=render_queue, capture_queue=capture_queue)
    checks = {
        "device_counts": {name: len(snapshot.devices) for name, snapshot in snapshots.items()},
        "input_only_seen": any(
            item.can_input and not item.can_output for item in snapshots["directional"].devices
        ),
        "output_only_seen": any(
            item.can_output and not item.can_input for item in snapshots["directional"].devices
        ),
        "duplex_seen": any(
            item.can_input and item.can_output for item in snapshots["many"].devices
        ),
        "ten_ms_samples": ten_ms.samples_per_frame,
        "twenty_ms_samples": twenty_ms.samples_per_frame,
        "timestamp_ordered": ordering == sorted(ordering),
        "overflow_seen": overflow_seen,
        "overflow_count": render_queue.overflow_count,
        "backend_capabilities": [item.public_dict() for item in detect_backend_capabilities()],
        "kws_first_hit": first is not None,
        "kws_cooldown_rejected": duplicate is None,
        "kws_later_hit": later is not None,
        "product_audio_topology_changed": False,
        "pcm_persisted": False,
        "terminal_zero": tracker.is_terminal_zero(
            render_queue=render_queue, capture_queue=capture_queue
        ),
        "state_projection": dict(
            state_projection(
                capture=CaptureActivity.INACTIVE,
                playback=PlaybackActivity.INACTIVE,
                processing=ProcessingState.BYPASS,
                route=AudioRouteState.READY,
            )
        ),
    }
    verified = all(
        (
            checks["device_counts"] == {"empty": 0, "one": 1, "directional": 2, "many": 3},
            checks["input_only_seen"],
            checks["output_only_seen"],
            checks["duplex_seen"],
            checks["ten_ms_samples"] == 160,
            checks["twenty_ms_samples"] == 320,
            checks["timestamp_ordered"],
            checks["overflow_seen"],
            checks["overflow_count"] == 1,
            checks["kws_first_hit"],
            checks["kws_cooldown_rejected"],
            checks["kws_later_hit"],
            checks["terminal_zero"],
        )
    )
    return ProbeReport(
        scenario=ProbeScenario.FAKE_CONTRACT,
        status=ProbeStatus.COMPLETE if verified else ProbeStatus.FAILED,
        platform_public=platform_name(),
        result=checks,
        terminal=terminal,
        error_code=None if verified else "fake_contract_failed",
    )


def private_identifier_digest(value: str) -> str:
    clean = str(value).strip().encode("utf-8", errors="replace")
    return hashlib.sha256(clean).hexdigest()[:16]


def redact_text(value: str) -> str:
    text = str(value)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(r"\1<redacted>", text)
    text = _GUID_PATTERN.sub("<private-id>", text)
    return text[:1000]


def sanitize_public_value(value: object, *, key: str = "") -> object:
    lowered = key.casefold()
    safe_metadata_keys = {
        "pcm_persisted",
        "payload_persisted",
        "idle_microphone_uploaded_frames",
        "product_uplink_frames",
    }
    if lowered not in safe_metadata_keys and any(
        fragment in lowered for fragment in _PRIVATE_KEY_FRAGMENTS
    ):
        if "id" in lowered and isinstance(value, str):
            return f"masked:{private_identifier_digest(value)}"
        return "<redacted>"
    if isinstance(value, bytes | bytearray | memoryview):
        return "<binary-redacted>"
    if isinstance(value, str):
        return redact_text(value)
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {
            redact_text(str(item_key))[:120]: sanitize_public_value(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, Iterable):
        return [sanitize_public_value(item) for item in list(value)[:PROBE_EVENT_CAPACITY]]
    return redact_text(type(value).__name__)


def ensure_probe_report_safe(value: Mapping[str, object]) -> None:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True)
    encoded = payload.encode("utf-8")
    if len(encoded) > PROBE_MAX_JSON_BYTES:
        raise ValueError("probe report exceeds bounded JSON size")
    lowered = payload.casefold()
    forbidden = ("authorization: bearer ", "password=", "api_key=", "raw_pcm")
    if any(marker in lowered for marker in forbidden):
        raise ValueError("probe report contains a forbidden private marker")
    if _GUID_PATTERN.search(payload):
        raise ValueError("probe report contains an unredacted private endpoint identifier")


def dumps_probe_report(report: ProbeReport) -> str:
    value = report.public_dict()
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def public_device_dict(device: AudioDeviceDescriptor) -> dict[str, object]:
    """Return a device card without exposing its opaque endpoint identity."""

    return {
        "device_key": f"masked:{private_identifier_digest(device.opaque_device_id)}",
        "public_name": redact_text(device.public_name)[:120],
        "platform": device.platform.value,
        "host_api": redact_text(device.host_api)[:80],
        "can_input": device.can_input,
        "can_output": device.can_output,
        "default_input": device.default_input,
        "default_output": device.default_output,
        "available": device.available,
        "route_class": device.route_class,
        "supported_formats": [item.public_dict() for item in device.supported_formats],
        "reported_input_latency_ms": device.reported_input_latency_ms,
        "reported_output_latency_ms": device.reported_output_latency_ms,
    }


def process_runtime_sample() -> dict[str, object]:
    """Return bounded process samples without adding psutil as a dependency."""

    rss_bytes: int | None = None
    try:
        import resource

        maximum = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        rss_bytes = maximum if sys.platform == "darwin" else maximum * 1024
    except (ImportError, OSError, ValueError):
        rss_bytes = None
    return {
        "process_cpu_seconds": round(time.process_time(), 6),
        "rss_bytes_sample": rss_bytes,
        "thread_count_sample": threading.active_count(),
    }


def processing_metrics_public(metrics: AudioProcessingMetrics) -> dict[str, object]:
    return {
        "backend_public_name": metrics.backend_public_name,
        "state": metrics.state.value,
        "aec_available": metrics.aec_available,
        "aec_effective": metrics.aec_effective,
        "ns_available": metrics.ns_available,
        "ns_effective": metrics.ns_effective,
        "agc_available": metrics.agc_available,
        "agc_effective": metrics.agc_effective,
        "render_frames": metrics.render_frames,
        "capture_frames": metrics.capture_frames,
        "processed_frames": metrics.processed_frames,
        "render_queue_peak": metrics.render_queue_peak,
        "capture_queue_peak": metrics.capture_queue_peak,
        "overflow_count": metrics.overflow_count,
        "estimated_delay_ms": metrics.estimated_delay_ms,
        "estimated_drift_ppm": metrics.estimated_drift_ppm,
        "error_code": metrics.error_code,
    }
