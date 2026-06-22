"""
Assistant event model for the PC App layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AssistantEvent:
    type: str
    payload: dict[str, Any]
