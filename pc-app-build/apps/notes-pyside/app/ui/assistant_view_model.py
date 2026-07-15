"""Qt-facing projection of the single-writer Assistant Runtime state."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from PySide6.QtCore import QObject, Property, Signal, Slot

from ..assistant import (
    AssistantConnectionStatus,
    AssistantController,
    AssistantPhase,
    AssistantRuntimeMode,
    AssistantState,
    redact_error_text,
)

CommandFactory = Callable[[], Awaitable[None]]

_PHASE_LABELS = {
    AssistantPhase.DISABLED: "已关闭",
    AssistantPhase.IDLE: "待机",
    AssistantPhase.ACTIVATING: "激活中",
    AssistantPhase.CONNECTING: "连接中",
    AssistantPhase.CONNECTED: "已连接",
    AssistantPhase.LISTENING: "正在提交",
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


class AssistantViewModel(QObject):
    """Expose immutable Runtime snapshots and dispatch commands to one controller.

    The ViewModel never keeps a second phase or connection state. Every product-facing
    property is derived from the latest ``AssistantController.state`` snapshot.
    """

    stateChanged = Signal()
    commandStateChanged = Signal()
    developerChanged = Signal()
    operationFailed = Signal(str, str)

    def __init__(self, controller: AssistantController) -> None:
        super().__init__()
        self._controller = controller
        self._state = controller.state
        self._tasks: set[asyncio.Task[None]] = set()
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

    def _set_operation_error(self, message: str) -> None:
        clean = str(message)
        if clean == self._operation_error:
            return
        self._operation_error = clean
        self.commandStateChanged.emit()


def _mask_value(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}***{value[-4:]}"
