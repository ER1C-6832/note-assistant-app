"""Typed activation request, response, and outcome models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class ActivationOutcomeStatus(str, Enum):
    ACTIVATED = "activated"
    REQUIRED = "required"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ActivationInfo:
    code: str
    challenge: str
    message: str = ""


@dataclass(frozen=True, slots=True)
class OtaResponse:
    websocket_url: str | None
    websocket_token: str | None
    activation: ActivationInfo | None
    redacted_json: str


@dataclass(frozen=True, slots=True)
class ActivationOutcome:
    status: ActivationOutcomeStatus
    message: str
    websocket_url_public: str | None = None
    activation_code: str | None = None
    authorization_url: str | None = None
    diagnostics_json_redacted: str | None = None


@dataclass(frozen=True, slots=True)
class HttpJsonResponse:
    status_code: int
    body: str


class ActivationClient(Protocol):
    async def run(self) -> ActivationOutcome: ...


class ActivationHttpTransport(Protocol):
    async def post_json(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> HttpJsonResponse: ...
