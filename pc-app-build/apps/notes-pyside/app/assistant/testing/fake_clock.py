"""Deterministic monotonic clock for Assistant Runtime tests."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class FakeClock:
    current_ns: int = 1_000_000_000

    def now_ns(self) -> int:
        return self.current_ns

    def advance_ns(self, value: int) -> int:
        if value < 0:
            raise ValueError("clock cannot move backwards")
        self.current_ns += value
        return self.current_ns

    def advance_ms(self, value: float) -> int:
        if value < 0:
            raise ValueError("clock cannot move backwards")
        return self.advance_ns(int(value * 1_000_000))
