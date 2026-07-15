"""Single-process Assistant Runtime core."""

from .activation import (
    ActivationError,
    ActivationOutcome,
    ActivationOutcomeStatus,
    FakeActivationClient,
    RealOtaActivationClient,
)
from .controller import AssistantController, ControllerClosedError
from .errors import AssistantErrorCode, redact_error_text
from .identity import DeviceIdentity, DeviceIdentityManager, DeviceIdentityStore
from .network import (
    PersistedConnectionConfigProvider,
    RealWebSocketTransport,
    ReconnectDecision,
    ReconnectPolicy,
    RuntimeTransportRouter,
    WebSocketConnectionConfig,
)
from .protocol import XiaozhiMessageBuilder, XiaozhiMessageRouter
from .preferences import (
    ASSISTANT_PREFERENCES_SCHEMA_VERSION,
    AssistantPreferences,
    AssistantPreferencesError,
    AssistantPreferencesStore,
)
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
from .state_machine import ConversationStateMachine

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
    "PersistedConnectionConfigProvider",
    "RealWebSocketTransport",
    "ReconnectDecision",
    "ReconnectPolicy",
    "RuntimeTransportRouter",
    "WebSocketConnectionConfig",
    "XiaozhiMessageBuilder",
    "XiaozhiMessageRouter",
    "MicrophoneOwner",
    "RealOtaActivationClient",
    "RealRuntimeConfig",
    "RuntimeConfigError",
    "RuntimeConfigStore",
    "StateInvariantError",
    "StreamingConversationState",
    "VoiceActivityState",
    "VoiceInteractionMode",
    "redact_error_text",
]
