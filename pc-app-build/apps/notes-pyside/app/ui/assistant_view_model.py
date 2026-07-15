"""Qt-facing projection of the single-writer Assistant Runtime state."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace

from PySide6.QtCore import QObject, Property, Signal, Slot

from ..assistant import (
    AssistantActivationStatus,
    AssistantCapability,
    AssistantAudioStatus,
    AssistantConnectionStatus,
    AssistantController,
    AssistantEntrySource,
    AssistantPhase,
    AssistantRuntimeMode,
    AssistantState,
    CapabilityStatus,
    StreamingConversationState,
    VoiceInteractionMode,
    redact_error_text,
)
from ..assistant.preferences import (
    AssistantPreferences,
    AssistantPreferencesStore,
    clamp_ratio,
)

CommandFactory = Callable[[], Awaitable[None]]

_PHASE_LABELS = {
    AssistantPhase.DISABLED: "已关闭",
    AssistantPhase.IDLE: "待机",
    AssistantPhase.ACTIVATING: "激活中",
    AssistantPhase.CONNECTING: "连接中",
    AssistantPhase.CONNECTED: "已连接",
    AssistantPhase.LISTENING: "聆听中",
    AssistantPhase.UPLOADING_AUDIO: "上传中",
    AssistantPhase.THINKING: "思考中",
    AssistantPhase.SPEAKING: "回复中",
    AssistantPhase.RECONNECTING: "重连中",
    AssistantPhase.ERROR: "发生错误",
}

_CONNECTION_LABELS = {
    AssistantConnectionStatus.DISCONNECTED: "未连接",
    AssistantConnectionStatus.CONNECTING: "连接中",
    AssistantConnectionStatus.CONNECTED: "已连接",
    AssistantConnectionStatus.CLOSING: "关闭中",
}


@dataclass(frozen=True, slots=True)
class _AuroraTarget:
    visual_state: str
    compact_label: str
    color_a: str
    color_b: str
    color_c: str
    scale: float
    speed: float
    alpha: float
    border_color: str


class AssistantViewModel(QObject):
    """Expose immutable Runtime snapshots and dispatch commands to one controller.

    The ViewModel never keeps a second phase or connection state. Every product-facing
    property is derived from the latest ``AssistantController.state`` snapshot.
    """

    stateChanged = Signal()
    commandStateChanged = Signal()
    developerChanged = Signal()
    preferencesChanged = Signal()
    operationFailed = Signal(str, str)

    def __init__(
        self,
        controller: AssistantController,
        *,
        preferences_store: AssistantPreferencesStore | None = None,
        initial_preferences: AssistantPreferences | None = None,
    ) -> None:
        super().__init__()
        self._controller = controller
        self._state = controller.state
        self._preferences_store = preferences_store
        self._preferences = initial_preferences or (
            preferences_store.load() if preferences_store is not None else AssistantPreferences()
        )
        self._tasks: set[asyncio.Task[None]] = set()
        self._position_save_task: asyncio.Task[None] | None = None
        self._launcher_position_dirty = False
        self._unsubscribe = controller.subscribe(self._accept_state)
        self._developer_expanded = False
        self._operation_error = ""
        self._closed = False

    @property
    def controller(self) -> AssistantController:
        return self._controller

    @Property(bool, notify=stateChanged)
    def enabled(self) -> bool:
        return self._state.enabled

    @Property(str, notify=stateChanged)
    def phase(self) -> str:
        return self._state.phase.value

    @Property(str, notify=stateChanged)
    def phaseText(self) -> str:
        return _PHASE_LABELS[self._state.phase]

    @Property(str, notify=stateChanged)
    def connectionStatus(self) -> str:
        return self._state.connection.status.value

    @Property(str, notify=stateChanged)
    def connectionStatusText(self) -> str:
        return _CONNECTION_LABELS[self._state.connection.status]

    @Property(bool, notify=stateChanged)
    def connected(self) -> bool:
        return self._state.is_connected

    @Property(bool, notify=stateChanged)
    def reconnecting(self) -> bool:
        return self._state.phase is AssistantPhase.RECONNECTING

    @Property(str, notify=stateChanged)
    def runtimeMode(self) -> str:
        return self._state.runtime_mode.value

    @Property(str, notify=stateChanged)
    def runtimeModeText(self) -> str:
        return "Scripted Fake" if self._state.runtime_mode is AssistantRuntimeMode.FAKE else "真实"

    @Property(str, notify=stateChanged)
    def voiceInteractionMode(self) -> str:
        return self._state.conversation.preferred_voice_mode.value

    @Property(bool, notify=stateChanged)
    def streamingBargeInEnabled(self) -> bool:
        return self._state.conversation.streaming_barge_in_enabled

    @Property(bool, notify=stateChanged)
    def streamingCapabilityReady(self) -> bool:
        return (
            self._state.capability_status(AssistantCapability.STREAMING_CONVERSATION)
            is CapabilityStatus.ACTIVE
        )

    @Property(bool, notify=stateChanged)
    def streamingConversationActive(self) -> bool:
        return self._state.conversation.streaming_session_active

    @Property(str, notify=stateChanged)
    def streamingConversationState(self) -> str:
        return self._state.conversation.streaming_state.value

    @Property(int, notify=stateChanged)
    def streamingTurnIndex(self) -> int:
        return self._state.conversation.streaming_turn_index

    @Property(str, notify=stateChanged)
    def vadState(self) -> str:
        return self._state.conversation.vad_state.value

    @Property(str, notify=stateChanged)
    def vadStatusText(self) -> str:
        return self._state.conversation.vad_status_text

    @Property(bool, notify=stateChanged)
    def canStartStreamingConversation(self) -> bool:
        return bool(
            self.streamingCapabilityReady
            and self._state.is_connected
            and self._state.conversation.preferred_voice_mode
            is VoiceInteractionMode.STREAMING_CONVERSATION
            and not self._state.conversation.streaming_session_active
            and self._state.conversation.active_text_turn_token is None
            and self._state.conversation.active_voice_turn_token is None
            and self._state.phase is AssistantPhase.CONNECTED
        )

    @Property(bool, notify=stateChanged)
    def canStopStreamingConversation(self) -> bool:
        return self._state.conversation.streaming_session_active

    @Property(bool, notify=preferencesChanged)
    def conversationTextEnabled(self) -> bool:
        return self._preferences.conversation_text_enabled

    @Property(bool, notify=preferencesChanged)
    def textInputEnabled(self) -> bool:
        return self._preferences.text_input_enabled

    @Property(float, notify=preferencesChanged)
    def launcherXRatio(self) -> float:
        return self._preferences.launcher_x_ratio

    @Property(float, notify=preferencesChanged)
    def launcherYRatio(self) -> float:
        return self._preferences.launcher_y_ratio

    @Property(str, notify=stateChanged)
    def auroraVisualState(self) -> str:
        return _aurora_target(self._state).visual_state

    @Property(str, notify=stateChanged)
    def compactStatusLabel(self) -> str:
        return _aurora_target(self._state).compact_label

    @Property(str, notify=stateChanged)
    def auroraColorA(self) -> str:
        return _aurora_target(self._state).color_a

    @Property(str, notify=stateChanged)
    def auroraColorB(self) -> str:
        return _aurora_target(self._state).color_b

    @Property(str, notify=stateChanged)
    def auroraColorC(self) -> str:
        return _aurora_target(self._state).color_c

    @Property(float, notify=stateChanged)
    def auroraScale(self) -> float:
        return _aurora_target(self._state).scale

    @Property(float, notify=stateChanged)
    def auroraSpeed(self) -> float:
        return _aurora_target(self._state).speed

    @Property(float, notify=stateChanged)
    def auroraAlpha(self) -> float:
        return _aurora_target(self._state).alpha

    @Property(str, notify=stateChanged)
    def auroraBorderColor(self) -> str:
        return _aurora_target(self._state).border_color

    @Property(str, notify=stateChanged)
    def statusText(self) -> str:
        return self._state.status_text

    @Property(bool, notify=stateChanged)
    def hasRuntimeError(self) -> bool:
        return self._state.error is not None

    @Property(str, notify=stateChanged)
    def errorCode(self) -> str:
        return self._state.error.code if self._state.error is not None else ""

    @Property(str, notify=stateChanged)
    def errorMessage(self) -> str:
        return self._state.error.message if self._state.error is not None else ""

    @Property(bool, notify=stateChanged)
    def errorRecoverable(self) -> bool:
        return bool(self._state.error and self._state.error.recoverable)

    @Property(str, notify=commandStateChanged)
    def operationError(self) -> str:
        return self._operation_error

    @Property(bool, notify=commandStateChanged)
    def commandBusy(self) -> bool:
        return any(not task.done() for task in self._tasks)

    @Property(bool, notify=stateChanged)
    def canConnect(self) -> bool:
        return (
            self._state.enabled
            and self._state.connection.status is AssistantConnectionStatus.DISCONNECTED
            and self._state.phase not in {AssistantPhase.ACTIVATING, AssistantPhase.RECONNECTING}
        )

    @Property(bool, notify=stateChanged)
    def canDisconnect(self) -> bool:
        return self._state.connection.status is not AssistantConnectionStatus.DISCONNECTED

    @Property(bool, notify=stateChanged)
    def canSendText(self) -> bool:
        return self._state.is_connected and self._state.phase is AssistantPhase.CONNECTED

    @Property(bool, notify=stateChanged)
    def canPushToTalk(self) -> bool:
        return bool(
            self._state.is_connected
            and self._state.conversation.preferred_voice_mode.value == "hold_to_talk"
            and self._state.phase is AssistantPhase.CONNECTED
            and self._state.conversation.active_text_turn_token is None
            and self._state.conversation.active_voice_turn_token is None
        )

    @Property(bool, notify=stateChanged)
    def pushToTalkActive(self) -> bool:
        return bool(
            self._state.conversation.active_entry_source is AssistantEntrySource.PUSH_TO_TALK
            and self._state.conversation.active_voice_turn_token is not None
        )

    @Property(bool, notify=stateChanged)
    def pushToTalkRecording(self) -> bool:
        return self._state.audio.status is AssistantAudioStatus.RECORDING

    @Property(bool, notify=stateChanged)
    def pushToTalkStopping(self) -> bool:
        return bool(
            self.pushToTalkActive
            and self._state.phase in {AssistantPhase.UPLOADING_AUDIO, AssistantPhase.THINKING}
        )

    @Property(str, notify=stateChanged)
    def inputDevicePublicName(self) -> str:
        return self._state.audio.input_device_public_name or ""

    @Property(int, notify=stateChanged)
    def capturedAudioFrames(self) -> int:
        return self._state.audio.captured_frames

    @Property(int, notify=stateChanged)
    def uploadedAudioFrames(self) -> int:
        return self._state.audio.uploaded_frames

    @Property(int, notify=stateChanged)
    def droppedPcmFrames(self) -> int:
        return self._state.audio.dropped_pcm_frames

    @Property(int, notify=stateChanged)
    def activeVoiceTurnToken(self) -> int:
        return self._state.conversation.active_voice_turn_token or 0

    @Property(bool, notify=stateChanged)
    def canRetry(self) -> bool:
        return self._state.enabled and (
            self._state.error is not None
            or self._state.connection.status is AssistantConnectionStatus.DISCONNECTED
        )

    @Property(str, notify=stateChanged)
    def lastUserText(self) -> str:
        return self._state.conversation.last_user_text or ""

    @Property(str, notify=stateChanged)
    def lastAssistantText(self) -> str:
        return self._state.conversation.last_assistant_text or ""

    @Property(str, notify=stateChanged)
    def lastAssistantSourceType(self) -> str:
        return self._state.conversation.last_assistant_source_type or ""

    @Property(str, notify=stateChanged)
    def deviceIdMasked(self) -> str:
        return self._state.identity.device_id_masked or ""

    @Property(str, notify=stateChanged)
    def clientIdMasked(self) -> str:
        return self._state.identity.client_id_masked or ""

    @Property(bool, notify=stateChanged)
    def identityReady(self) -> bool:
        return self._state.identity.identity_ready

    @Property(str, notify=stateChanged)
    def sessionIdMasked(self) -> str:
        return _mask_value(self._state.connection.session_id)

    @Property(str, notify=stateChanged)
    def websocketUrl(self) -> str:
        return self._state.connection.websocket_url_public or ""

    @Property(str, notify=stateChanged)
    def activationStatus(self) -> str:
        return self._state.activation.status.value

    @Property(str, notify=stateChanged)
    def activationCode(self) -> str:
        return self._state.activation.activation_code or ""

    @Property(str, notify=stateChanged)
    def activationMessage(self) -> str:
        return self._state.activation.message or ""

    @Property(str, notify=stateChanged)
    def activationUrl(self) -> str:
        return self._state.activation.authorization_url or ""

    @Property(int, notify=stateChanged)
    def reconnectAttempt(self) -> int:
        return self._state.recovery.reconnect_attempt

    @Property(str, notify=stateChanged)
    def reconnectDecision(self) -> str:
        return self._state.recovery.last_reconnect_decision or ""

    @Property(str, notify=stateChanged)
    def lastProtocolEvent(self) -> str:
        return self._state.protocol.last_protocol_event or ""

    @Property(str, notify=stateChanged)
    def lastClientJsonRedacted(self) -> str:
        return self._state.protocol.last_client_json_redacted or ""

    @Property(str, notify=stateChanged)
    def lastServerJsonRedacted(self) -> str:
        return self._state.protocol.last_server_json_redacted or ""

    @Property(str, notify=stateChanged)
    def lastProtocolError(self) -> str:
        return self._state.protocol.last_protocol_error or ""

    @Property("QVariantList", notify=stateChanged)
    def capabilityItems(self) -> list[dict[str, object]]:
        return [
            {
                "name": item.name.value,
                "status": item.status.value,
                "targetGate": item.target_gate,
                "detail": item.detail,
            }
            for item in self._state.capabilities
        ]

    @Property(bool, notify=developerChanged)
    def developerExpanded(self) -> bool:
        return self._developer_expanded

    @developerExpanded.setter
    def developerExpanded(self, expanded: bool) -> None:
        value = bool(expanded)
        if value == self._developer_expanded:
            return
        self._developer_expanded = value
        self.developerChanged.emit()

    @Slot()
    def initialize(self) -> None:
        self._schedule("initialize", self._initialize_runtime)

    @Slot(bool)
    def requestSetEnabled(self, enabled: bool) -> None:
        async def command() -> None:
            if enabled:
                await self._controller.enable_assistant()
                await self._controller.ensure_device_identity()
            else:
                await self._controller.disable_assistant()

        self._schedule("set_enabled", command)

    @Slot()
    def requestConnect(self) -> None:
        async def command() -> None:
            if not self._controller.state.enabled:
                await self._controller.enable_assistant()
            if not self._controller.state.identity.identity_ready:
                await self._controller.ensure_device_identity()
            await self._controller.connect()

        self._schedule("connect", command)

    @Slot()
    def requestDisconnect(self) -> None:
        self._schedule(
            "disconnect",
            lambda: self._controller.disconnect("assistant_panel_user_disconnect"),
        )

    @Slot()
    def requestRetry(self) -> None:
        async def command() -> None:
            if not self._controller.state.enabled:
                await self._controller.enable_assistant()
            await self._controller.reconnect()

        self._schedule("retry", command)

    @Slot(str)
    def requestVoiceInteractionMode(self, mode: str) -> None:
        normalized = str(mode).strip().lower()
        try:
            selected = VoiceInteractionMode(normalized)
        except ValueError:
            self._set_operation_error(f"未知语音模式：{mode}")
            return
        self._schedule(
            "set_voice_interaction_mode",
            lambda: self._controller.set_voice_interaction_mode(selected),
        )

    @Slot(bool)
    def requestStreamingBargeInEnabled(self, enabled: bool) -> None:
        self._schedule(
            "set_streaming_barge_in",
            lambda: self._controller.set_streaming_barge_in_enabled(bool(enabled)),
        )

    @Slot(float, float)
    def requestLauncherPosition(self, x_ratio: float, y_ratio: float) -> None:
        next_preferences = replace(
            self._preferences,
            launcher_x_ratio=clamp_ratio(x_ratio),
            launcher_y_ratio=clamp_ratio(y_ratio),
        )
        if next_preferences == self._preferences:
            return
        self._preferences = next_preferences
        self._launcher_position_dirty = True
        self.preferencesChanged.emit()
        self._schedule_launcher_position_save()

    @Slot()
    def requestPushToTalkStart(self) -> None:
        self._schedule(
            "push_to_talk_start",
            lambda: self._controller.start_push_to_talk(permission_granted=True),
        )

    @Slot()
    def requestPushToTalkStop(self) -> None:
        self._schedule("push_to_talk_stop", self._controller.stop_push_to_talk)

    @Slot()
    def requestStreamingConversationStart(self) -> None:
        self._schedule(
            "streaming_conversation_start",
            lambda: self._controller.start_streaming_conversation(permission_granted=True),
        )

    @Slot()
    def requestStreamingConversationStop(self) -> None:
        self._schedule(
            "streaming_conversation_stop",
            lambda: self._controller.stop_streaming_conversation("user_stop"),
        )

    @Slot()
    def requestStreamingConversationToggle(self) -> None:
        if self._state.conversation.streaming_session_active:
            self.requestStreamingConversationStop()
        else:
            self.requestStreamingConversationStart()

    @Slot(str)
    def requestSendText(self, text: str) -> None:
        clean = str(text).strip()
        if not clean:
            self._set_operation_error("请输入要发送的内容")
            return
        self._schedule("send_text", lambda: self._controller.send_text(clean))

    @Slot(str)
    def requestRuntimeMode(self, mode: str) -> None:
        normalized = str(mode).strip().lower()
        if normalized == AssistantRuntimeMode.FAKE.value:
            self._schedule("use_fake_runtime", self._controller.use_fake_runtime)
            return
        if normalized == AssistantRuntimeMode.REAL.value:
            self._schedule("use_real_runtime", self._controller.use_real_runtime)
            return
        self._set_operation_error(f"未知 Runtime 模式：{mode}")

    @Slot()
    def requestRunActivation(self) -> None:
        if self._state.runtime_mode is AssistantRuntimeMode.FAKE:
            self._schedule("fake_activation", self._controller.run_fake_activation)
        else:
            self._schedule("real_activation", self._controller.run_real_activation)

    @Slot()
    def requestResetIdentity(self) -> None:
        self._schedule("reset_identity", self._controller.reset_device_identity)

    @Slot()
    def requestSimulateAbnormalClose(self) -> None:
        self._schedule(
            "simulate_abnormal_close",
            lambda: self._controller.simulate_connection_closed(
                code=1012,
                reason="assistant_panel_simulated_close",
            ),
        )

    @Slot()
    def requestSimulateFailure(self) -> None:
        self._schedule(
            "simulate_failure",
            lambda: self._controller.simulate_connection_failure(
                "assistant_panel_simulated_transport_failure"
            ),
        )

    @Slot()
    def clearOperationError(self) -> None:
        self._set_operation_error("")

    async def close(self) -> None:
        if self._closed:
            return
        position_task = self._position_save_task
        self._position_save_task = None
        if position_task is not None and not position_task.done():
            position_task.cancel()
            await asyncio.gather(position_task, return_exceptions=True)
        if self._launcher_position_dirty:
            try:
                await asyncio.wait_for(self._persist_launcher_position(), timeout=1.5)
            except Exception as exc:
                self._set_operation_error(redact_error_text(str(exc) or type(exc).__name__))
        self._closed = True
        self._unsubscribe()
        tasks = tuple(task for task in self._tasks if not task.done())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        self.commandStateChanged.emit()

    async def _initialize_runtime(self) -> None:
        await self._controller.start()
        await self._controller.ensure_device_identity()

    def _accept_state(self, state: AssistantState) -> None:
        if self._closed:
            return
        self._state = state
        self.stateChanged.emit()

    def _schedule(self, operation: str, factory: CommandFactory) -> None:
        if self._closed:
            self._set_operation_error("AssistantViewModel 已关闭")
            return
        self._set_operation_error("")

        async def execute() -> None:
            try:
                await factory()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                message = redact_error_text(str(exc) or type(exc).__name__)
                self._set_operation_error(message)
                self.operationFailed.emit(operation, message)

        try:
            task = asyncio.create_task(execute(), name=f"assistant-ui-{operation}")
        except RuntimeError as exc:
            self._set_operation_error(redact_error_text(exc))
            return
        self._tasks.add(task)
        self.commandStateChanged.emit()

        def completed(done: asyncio.Task[None]) -> None:
            self._tasks.discard(done)
            self.commandStateChanged.emit()

        task.add_done_callback(completed)

    def _schedule_launcher_position_save(self) -> None:
        if self._preferences_store is None or self._closed:
            return
        existing = self._position_save_task
        if existing is not None and not existing.done():
            existing.cancel()

        async def save_after_debounce() -> None:
            try:
                await asyncio.sleep(0.25)
                await self._persist_launcher_position()
            except asyncio.CancelledError:
                raise

        coroutine = save_after_debounce()
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.get_event_loop()
            task = loop.create_task(
                coroutine,
                name="assistant-ui-save-launcher-position",
            )
        except RuntimeError as exc:
            coroutine.close()
            self._set_operation_error(redact_error_text(exc))
            return
        self._position_save_task = task

        def completed(done: asyncio.Task[None]) -> None:
            if self._position_save_task is done:
                self._position_save_task = None
            if done.cancelled():
                return
            error = done.exception()
            if error is not None:
                self._set_operation_error(redact_error_text(str(error) or type(error).__name__))

        task.add_done_callback(completed)

    async def _persist_launcher_position(self) -> None:
        store = self._preferences_store
        if store is None or not self._launcher_position_dirty:
            return
        saved = await asyncio.to_thread(
            store.update_launcher_position,
            self._preferences.launcher_x_ratio,
            self._preferences.launcher_y_ratio,
        )
        self._preferences = replace(
            self._preferences,
            launcher_x_ratio=saved.launcher_x_ratio,
            launcher_y_ratio=saved.launcher_y_ratio,
        )
        self._launcher_position_dirty = False
        self.preferencesChanged.emit()

    def _set_operation_error(self, message: str) -> None:
        clean = str(message)
        if clean == self._operation_error:
            return
        self._operation_error = clean
        self.commandStateChanged.emit()


def _aurora_target(state: AssistantState) -> _AuroraTarget:
    if state.activation.status is AssistantActivationStatus.REQUIRED:
        return _AuroraTarget(
            "activation_required",
            "激活",
            "#FFC857",
            "#A78BFA",
            "#00000000",
            0.96,
            0.45,
            1.0,
            "#B88912",
        )
    if state.phase is AssistantPhase.ERROR or state.audio.status is AssistantAudioStatus.ERROR:
        return _AuroraTarget(
            "error",
            "重试",
            "#F45B69",
            "#6B7280",
            "#00000000",
            0.92,
            0.55,
            1.0,
            "#D13D4D",
        )
    if state.conversation.streaming_state is StreamingConversationState.RECOVERING:
        return _AuroraTarget(
            "recovering",
            "恢复",
            "#3A86FF",
            "#6B7280",
            "#FFC857",
            0.96,
            0.72,
            0.96,
            "#5676A8",
        )
    if state.conversation.streaming_state is StreamingConversationState.USER_SPEAKING:
        return _AuroraTarget(
            "user_speaking",
            "聆听",
            "#FFA07A",
            "#3A86FF",
            "#A78BFA",
            1.14,
            1.15,
            1.0,
            "#E58263",
        )
    if (
        state.phase is AssistantPhase.LISTENING
        or state.audio.status is AssistantAudioStatus.RECORDING
    ):
        return _AuroraTarget(
            "listening",
            "聆听",
            "#FFA07A",
            "#3A86FF",
            "#00000000",
            1.12,
            1.1,
            1.0,
            "#E58263",
        )
    if state.phase is AssistantPhase.SPEAKING or state.audio.status is AssistantAudioStatus.PLAYING:
        return _AuroraTarget(
            "speaking",
            "回复",
            "#FFA07A",
            "#A78BFA",
            "#FFC857",
            1.05,
            0.85,
            1.0,
            "#D39B32",
        )
    if state.phase in {AssistantPhase.THINKING, AssistantPhase.UPLOADING_AUDIO}:
        return _AuroraTarget(
            "thinking",
            "思考",
            "#3A86FF",
            "#A78BFA",
            "#00000000",
            1.05,
            0.95,
            0.98,
            "#7967C7",
        )
    if (
        state.phase
        in {
            AssistantPhase.ACTIVATING,
            AssistantPhase.CONNECTING,
            AssistantPhase.RECONNECTING,
        }
        or state.connection.status is AssistantConnectionStatus.CONNECTING
    ):
        return _AuroraTarget(
            "connecting",
            "连接",
            "#3A86FF",
            "#FFC857",
            "#00000000",
            0.98,
            0.72,
            0.95,
            "#4B76C7",
        )
    if state.is_connected:
        return _AuroraTarget(
            "online",
            "在线",
            "#3A86FF",
            "#A78BFA",
            "#00000000",
            1.0,
            0.32,
            0.98,
            "#5579B8",
        )
    return _AuroraTarget(
        "idle",
        "待命" if state.enabled else "关闭",
        "#5B8DEF",
        "#6B7280",
        "#00000000",
        0.88,
        0.18,
        0.78,
        "#9AA5B5",
    )


def _mask_value(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}***{value[-4:]}"
