"""Reducer transition value objects."""

from __future__ import annotations

from dataclasses import dataclass

from .effects import AssistantEffect
from .state import AssistantState


@dataclass(frozen=True, slots=True)
class Transition:
    state: AssistantState
    effects: tuple[AssistantEffect, ...] = ()

    def validated(self) -> "Transition":
        self.state.validate()
        return self

    @classmethod
    def unchanged(cls, state: AssistantState) -> "Transition":
        return cls(state=state)
