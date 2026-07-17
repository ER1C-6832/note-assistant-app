"""Single-process Assistant Runtime core."""

from .activation import (
    ActivationError,
    ActivationOutcome,
    ActivationOutcomeStatus,
    FakeActivationClient,
    RealOtaActivationClient,
)
from .controller import ControllerClosedError
from .errors import AssistantErrorCode, redact_error_text
from .identity import DeviceIdentity, DeviceIdentityManager, DeviceIdentityStore
from .mcp import McpCoordinator, McpScriptedFakeTransport, ToolRegistry
from .mcp.transport_adapters import McpRealWebSocketTransport as RealWebSocketTransport
from .network import (
    PersistedConnectionConfigProvider,
    ReconnectDecision,
    ReconnectPolicy,
    RuntimeTransportRouter,
    WebSocketConnectionConfig,
)
from .playback.two_turn_controller import AssistantController, ConversationStateMachine
from .preferences import (
    ASSISTANT_PREFERENCES_SCHEMA_VERSION,
    AssistantPreferences,
    AssistantPreferencesError,
    AssistantPreferencesStore,
)
from .protocol import XiaozhiMessageBuilder, XiaozhiMessageRouter
from .runtime_config import (
    AssistantRuntimeConfig,
    FakeRuntimeConfig,
    RealRuntimeConfig,
    RuntimeConfigError,
    RuntimeConfigStore,
)
from .state import (
    AssistantActivationStatus,
    AssistantAudioStatus,
    AssistantCapability,
    AssistantConnectionStatus,
    AssistantEntrySource,
    AssistantError,
    AssistantErrorCategory,
    AssistantPhase,
    AssistantRuntimeMode,
    AssistantState,
    CapabilityState,
    CapabilityStatus,
    MicrophoneOwner,
    StateInvariantError,
    StreamingConversationState,
    VoiceActivityState,
    VoiceInteractionMode,
)

__all__ = [
    "ActivationError",
    "ActivationOutcome",
    "ActivationOutcomeStatus",
    "AssistantActivationStatus",
    "AssistantAudioStatus",
    "AssistantCapability",
    "AssistantConnectionStatus",
    "AssistantController",
    "AssistantEntrySource",
    "AssistantError",
    "AssistantErrorCode",
    "AssistantErrorCategory",
    "AssistantPhase",
    "AssistantPreferences",
    "AssistantPreferencesError",
    "AssistantPreferencesStore",
    "ASSISTANT_PREFERENCES_SCHEMA_VERSION",
    "AssistantRuntimeConfig",
    "AssistantRuntimeMode",
    "AssistantState",
    "CapabilityState",
    "CapabilityStatus",
    "ControllerClosedError",
    "ConversationStateMachine",
    "DeviceIdentity",
    "DeviceIdentityManager",
    "DeviceIdentityStore",
    "FakeActivationClient",
    "FakeRuntimeConfig",
    "McpCoordinator",
    "McpScriptedFakeTransport",
    "MicrophoneOwner",
    "PersistedConnectionConfigProvider",
    "RealOtaActivationClient",
    "RealRuntimeConfig",
    "RealWebSocketTransport",
    "ReconnectDecision",
    "ReconnectPolicy",
    "RuntimeConfigError",
    "RuntimeConfigStore",
    "RuntimeTransportRouter",
    "StateInvariantError",
    "StreamingConversationState",
    "ToolRegistry",
    "VoiceActivityState",
    "VoiceInteractionMode",
    "WebSocketConnectionConfig",
    "XiaozhiMessageBuilder",
    "XiaozhiMessageRouter",
    "redact_error_text",
]
