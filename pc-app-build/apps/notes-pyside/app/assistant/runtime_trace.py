"""Small redacted JSONL trace for runtime/audio lifecycle diagnosis."""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


class RuntimeTrace:
    def __init__(self, path: str | Path | None) -> None:
        self._path = Path(path) if path else None
        self._lock = threading.Lock()
        self._handle = None
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            if self._path.exists() and self._path.stat().st_size > 5_000_000:
                previous = self._path.with_suffix(self._path.suffix + ".1")
                previous.unlink(missing_ok=True)
                self._path.replace(previous)
            self._handle = self._path.open("a", encoding="utf-8", buffering=1)
        except OSError:
            self._handle = None

    def event(self, *, event: Any, before: Any, after: Any, effects: tuple[Any, ...]) -> None:
        handle = self._handle
        if handle is None:
            return
        item = {
            "at": datetime.now().astimezone().isoformat(),
            "event": type(event).__name__,
            "event_at_ns": getattr(event, "at_ns", None),
            "connection_generation": getattr(event, "connection_generation", None),
            "generation": getattr(event, "generation", None),
            "capture_generation": getattr(event, "capture_generation", None),
            "playback_generation": getattr(event, "playback_generation", None),
            "turn_token": getattr(event, "turn_token", None),
            "tts_state": (
                getattr(event, "state", None)
                if type(event).__name__ == "TtsStateReceived"
                else None
            ),
            "binary_size_bytes": (
                getattr(event, "size_bytes", None)
                if type(event).__name__ == "BinaryAudioReceived"
                else None
            ),
            "code": getattr(event, "code", None),
            "reason": getattr(event, "reason", None),
            "phase_before": getattr(getattr(before, "phase", None), "value", None),
            "phase_after": getattr(getattr(after, "phase", None), "value", None),
            "audio_before": getattr(
                getattr(getattr(before, "audio", None), "status", None), "value", None
            ),
            "audio_after": getattr(
                getattr(getattr(after, "audio", None), "status", None), "value", None
            ),
            "pending_completion_after": getattr(
                getattr(after, "conversation", None),
                "pending_voice_turn_completion_token",
                None,
            ),
            "protocol_after": getattr(
                getattr(after, "protocol", None), "last_protocol_event", None
            ),
            "error_after": getattr(getattr(after, "error", None), "code", None),
            "effects": [type(effect).__name__ for effect in effects],
        }
        try:
            encoded = json.dumps(
                {key: value for key, value in item.items() if value is not None},
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )
            with self._lock:
                handle.write(encoded + "\n")
        except (OSError, ValueError):
            return

    def close(self) -> None:
        handle = self._handle
        self._handle = None
        if handle is None:
            return
        try:
            handle.close()
        except OSError:
            pass
