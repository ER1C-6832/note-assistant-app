"""Versioned, device-local Assistant product preferences for Gate 3.1."""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Callable

from .state import VoiceInteractionMode

ASSISTANT_PREFERENCES_SCHEMA_VERSION = 1
DEFAULT_STREAMING_IDLE_TIMEOUT_MS = 8_000
MIN_STREAMING_IDLE_TIMEOUT_MS = 2_000
MAX_STREAMING_IDLE_TIMEOUT_MS = 60_000


class AssistantPreferencesError(ValueError):
    """Raised when Assistant preferences cannot be persisted safely."""


@dataclass(frozen=True, slots=True)
class AssistantPreferences:
    """Preferences that are independent from identity and transport credentials."""

    schema_version: int = ASSISTANT_PREFERENCES_SCHEMA_VERSION
    voice_interaction_mode: VoiceInteractionMode = VoiceInteractionMode.HOLD_TO_TALK
    streaming_idle_timeout_ms: int = DEFAULT_STREAMING_IDLE_TIMEOUT_MS
    streaming_barge_in_enabled: bool = False
    conversation_text_enabled: bool = True
    text_input_enabled: bool = True
    launcher_x_ratio: float = 1.0
    launcher_y_ratio: float = 1.0

    def normalized(self) -> "AssistantPreferences":
        return replace(
            self,
            schema_version=ASSISTANT_PREFERENCES_SCHEMA_VERSION,
            streaming_idle_timeout_ms=_clamp_int(
                self.streaming_idle_timeout_ms,
                MIN_STREAMING_IDLE_TIMEOUT_MS,
                MAX_STREAMING_IDLE_TIMEOUT_MS,
            ),
            launcher_x_ratio=clamp_ratio(self.launcher_x_ratio),
            launcher_y_ratio=clamp_ratio(self.launcher_y_ratio),
        )

    def to_json_dict(self) -> dict[str, object]:
        payload = asdict(self.normalized())
        payload["voice_interaction_mode"] = self.voice_interaction_mode.value
        return payload


PreferencesMutator = Callable[[AssistantPreferences], AssistantPreferences]


class AssistantPreferencesStore:
    """Atomically read and update ``assistant_preferences.json``.

    The store is deliberately synchronous and thread-safe. Qt/qasync callers use
    ``asyncio.to_thread`` so file I/O never blocks the UI event loop.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = threading.RLock()

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> AssistantPreferences:
        with self._lock:
            return self._load_unlocked()

    def save(self, preferences: AssistantPreferences) -> AssistantPreferences:
        normalized = preferences.normalized()
        with self._lock:
            self._save_unlocked(normalized)
        return normalized

    def update(self, mutator: PreferencesMutator) -> AssistantPreferences:
        with self._lock:
            current = self._load_unlocked()
            updated = mutator(current).normalized()
            self._save_unlocked(updated)
            return updated

    def update_voice_interaction_mode(
        self,
        mode: VoiceInteractionMode,
    ) -> AssistantPreferences:
        return self.update(lambda current: replace(current, voice_interaction_mode=mode))

    def update_streaming_barge_in_enabled(self, enabled: bool) -> AssistantPreferences:
        return self.update(
            lambda current: replace(current, streaming_barge_in_enabled=bool(enabled))
        )

    def update_launcher_position(self, x_ratio: float, y_ratio: float) -> AssistantPreferences:
        return self.update(
            lambda current: replace(
                current,
                launcher_x_ratio=clamp_ratio(x_ratio),
                launcher_y_ratio=clamp_ratio(y_ratio),
            )
        )

    def update_text_preferences(
        self,
        *,
        conversation_text_enabled: bool | None = None,
        text_input_enabled: bool | None = None,
    ) -> AssistantPreferences:
        def mutate(current: AssistantPreferences) -> AssistantPreferences:
            return replace(
                current,
                conversation_text_enabled=(
                    current.conversation_text_enabled
                    if conversation_text_enabled is None
                    else bool(conversation_text_enabled)
                ),
                text_input_enabled=(
                    current.text_input_enabled
                    if text_input_enabled is None
                    else bool(text_input_enabled)
                ),
            )

        return self.update(mutate)

    def _load_unlocked(self) -> AssistantPreferences:
        if not self._path.is_file():
            return AssistantPreferences()
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return AssistantPreferences()
        return _preferences_from_json(payload)

    def _save_unlocked(self, preferences: AssistantPreferences) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_name(f".{self._path.name}.tmp")
        data = json.dumps(
            preferences.to_json_dict(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(data)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._path)
        except OSError as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise AssistantPreferencesError(
                f"无法保存 Assistant 偏好：{type(exc).__name__}"
            ) from exc


def clamp_ratio(value: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 1.0
    if numeric != numeric:  # NaN
        return 1.0
    return max(0.0, min(1.0, numeric))


def _preferences_from_json(payload: object) -> AssistantPreferences:
    if not isinstance(payload, dict):
        return AssistantPreferences()
    schema_version = _safe_int(payload.get("schema_version"), default=1)
    if schema_version != ASSISTANT_PREFERENCES_SCHEMA_VERSION:
        return AssistantPreferences()

    mode_value = str(payload.get("voice_interaction_mode", "")).strip()
    try:
        mode = VoiceInteractionMode(mode_value)
    except ValueError:
        mode = VoiceInteractionMode.HOLD_TO_TALK

    return AssistantPreferences(
        voice_interaction_mode=mode,
        streaming_idle_timeout_ms=_clamp_int(
            _safe_int(
                payload.get("streaming_idle_timeout_ms"),
                default=DEFAULT_STREAMING_IDLE_TIMEOUT_MS,
            ),
            MIN_STREAMING_IDLE_TIMEOUT_MS,
            MAX_STREAMING_IDLE_TIMEOUT_MS,
        ),
        streaming_barge_in_enabled=_safe_bool(
            payload.get("streaming_barge_in_enabled"),
            default=False,
        ),
        conversation_text_enabled=_safe_bool(
            payload.get("conversation_text_enabled"),
            default=True,
        ),
        text_input_enabled=_safe_bool(
            payload.get("text_input_enabled"),
            default=True,
        ),
        launcher_x_ratio=clamp_ratio(payload.get("launcher_x_ratio", 1.0)),
        launcher_y_ratio=clamp_ratio(payload.get("launcher_y_ratio", 1.0)),
    )


def _safe_int(value: Any, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _safe_bool(value: Any, *, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))
