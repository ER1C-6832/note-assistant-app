from __future__ import annotations

from PySide6.QtCore import Slot

from app.services.sidecar_client import SidecarClient


class ContinuousSidecarClient(SidecarClient):
    """SidecarClient with optional continuous conversation start mode.

    Phase 9.3.1:
    The existing py-xiaozhi/PCBridge chain already supports ListeningMode.REALTIME
    via start_listen mode="realtime". This subclass only changes the default
    click-to-talk start mode when the UI preference is enabled.
    """

    def __init__(self, *args, voice_mode_controller=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._voice_mode_controller = voice_mode_controller

    def _continuous_conversation_enabled(self) -> bool:
        controller = getattr(self, "_voice_mode_controller", None)
        if controller is None:
            return False
        try:
            return bool(controller.continuousConversationEnabled)
        except Exception:
            return False

    @Slot()
    def startListen(self) -> None:
        if not self._can_control_voice():
            self._show_runtime_not_ready()
            return

        if self._voice_button_state in {"starting", "listening"}:
            self._last_control_text = "已经在聆听中"
            self._last_event_text = self._last_control_text
            self.statusChanged.emit()
            return

        mode = "realtime" if self._continuous_conversation_enabled() else "manual"

        self._note_command("start_listen")
        self._set_pending("start_listen")
        self._voice_button_state = "starting"
        self._assistant_status_text = "正在请求开始连续聆听" if mode == "realtime" else "正在请求开始聆听"
        self._queue_control("start_listen", mode=mode)
