from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from app.assistant import AssistantController  # noqa: E402
from app.assistant.state import (  # noqa: E402
    AssistantCapability,
    CapabilityStatus,
)
from app.assistant.testing import ScriptedFakeTransport  # noqa: E402
from app.ui import AssistantViewModel  # noqa: E402


@pytest.mark.asyncio
async def test_streaming_capability_is_active_and_view_model_projects_true() -> None:
    transport = ScriptedFakeTransport()
    controller = AssistantController(transport=transport, clock=transport.clock)
    view_model = AssistantViewModel(controller)
    try:
        assert (
            controller.state.capability_status(AssistantCapability.STREAMING_CONVERSATION)
            is CapabilityStatus.ACTIVE
        )
        assert view_model.streamingCapabilityReady is True
        assert (
            controller.state.capability_status(AssistantCapability.TTS_PLAYBACK)
            is CapabilityStatus.NOT_READY
        )
        assert (
            controller.state.capability_status(AssistantCapability.BARGE_IN)
            is CapabilityStatus.NOT_READY
        )
    finally:
        await view_model.close()
        await controller.shutdown()
