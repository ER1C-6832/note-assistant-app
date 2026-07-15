"""Product transcript helpers shared by Fake and Real text turns."""

from __future__ import annotations

import re

_TERMINAL_TTS_STATES = frozenset({"stop", "end", "finished", "done"})
_READABLE_PATTERN = re.compile(r"[\w\u3400-\u4dbf\u4e00-\u9fff]", re.UNICODE)


def has_readable_transcript_text(value: str | None) -> bool:
    """Return true when text contains readable words or CJK characters."""

    return bool(value and _READABLE_PATTERN.search(value.strip()))


def merge_assistant_transcript(existing: str | None, incoming: str | None) -> str:
    """Merge streaming text chunks without duplicating equal or overlapping content."""

    current = (existing or "").strip()
    chunk = (incoming or "").strip()
    if not chunk:
        return current
    if not current:
        return chunk
    if chunk == current or current.endswith(chunk):
        return current
    if chunk.startswith(current):
        return chunk

    maximum = min(len(current), len(chunk))
    for overlap in range(maximum, 0, -1):
        if current[-overlap:] == chunk[:overlap]:
            return f"{current}{chunk[overlap:]}"

    separator = " " if current[-1:].isascii() and chunk[:1].isascii() else ""
    return f"{current}{separator}{chunk}"


def is_terminal_tts_state(state: str | None) -> bool:
    return (state or "").strip().lower() in _TERMINAL_TTS_STATES
