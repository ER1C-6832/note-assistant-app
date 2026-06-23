"""
WebSocket client for the PC Assistant Sidecar.

This client runs in a background Python thread and exposes simple Qt properties
for QML. It listens for notes_changed and lets the app refresh notes
automatically when py-xiaozhi updates Notes API through MCP tools.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from typing import Any

import websockets
from PySide6.QtCore import QObject, Property, Signal, Slot


class SidecarClient(QObject):
    connectedChanged = Signal()
    statusChanged = Signal()
    notesChanged = Signal()

    _raw_message_received = Signal(str)
    _connection_changed = Signal(bool)
    _error_received = Signal(str)

    def __init__(self, ws_url: str | None = None) -> None:
        super().__init__()
        self._ws_url = ws_url or os.getenv("SIDECAR_WS_URL", "ws://127.0.0.1:17890/assistant")
        self._connected = False
        self._status_text = "Sidecar 未连接"
        self._assistant_status_text = "语音助手未连接"
        self._notes_api_status_text = "Notes API 未确认"
        self._py_xiaozhi_status_text = "py-xiaozhi 未确认"
        self._notes_tool_status_text = "notes 工具未确认"
        self._last_event_text = ""
        self._error_message = ""
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        self._raw_message_received.connect(self._handle_raw_message)
        self._connection_changed.connect(self._set_connected)
        self._error_received.connect(self._set_error)

    @Property(str, notify=statusChanged)
    def wsUrl(self) -> str:
        return self._ws_url

    @Property(bool, notify=connectedChanged)
    def connected(self) -> bool:
        return self._connected

    @Property(str, notify=statusChanged)
    def statusText(self) -> str:
        return self._status_text

    @Property(str, notify=statusChanged)
    def assistantStatusText(self) -> str:
        return self._assistant_status_text

    @Property(str, notify=statusChanged)
    def notesApiStatusText(self) -> str:
        return self._notes_api_status_text

    @Property(str, notify=statusChanged)
    def pyXiaozhiStatusText(self) -> str:
        return self._py_xiaozhi_status_text

    @Property(str, notify=statusChanged)
    def notesToolStatusText(self) -> str:
        return self._notes_tool_status_text

    @Property(str, notify=statusChanged)
    def lastEventText(self) -> str:
        return self._last_event_text

    @Property(str, notify=statusChanged)
    def errorMessage(self) -> str:
        return self._error_message

    @Slot()
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_thread, daemon=True)
        self._thread.start()

    @Slot()
    def stop(self) -> None:
        self._stop_event.set()

    @Slot()
    def refreshStatus(self) -> None:
        # The background loop sends refresh_status right after connect.
        # This slot remains for QML buttons; reconnecting is enough in 5.1.1.
        if not self._connected:
            self.start()

    def _run_thread(self) -> None:
        asyncio.run(self._connection_loop())

    async def _connection_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                async with websockets.connect(
                    self._ws_url,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=2,
                ) as websocket:
                    self._connection_changed.emit(True)
                    await websocket.send(json.dumps({"type": "refresh_status"}, ensure_ascii=False))

                    async for message in websocket:
                        if self._stop_event.is_set():
                            break
                        self._raw_message_received.emit(str(message))
            except Exception as exc:
                self._connection_changed.emit(False)
                self._error_received.emit(str(exc))

            if not self._stop_event.is_set():
                await asyncio.sleep(3)

    def _set_connected(self, connected: bool) -> None:
        if self._connected == connected:
            return

        self._connected = connected

        if connected:
            self._status_text = "Sidecar 已连接"
            self._assistant_status_text = "语音运行时检测中"
            self._error_message = ""
        else:
            self._status_text = "Sidecar 未连接"
            self._assistant_status_text = "语音助手未连接"

        self.connectedChanged.emit()
        self.statusChanged.emit()

    def _set_error(self, message: str) -> None:
        if not message:
            return

        self._error_message = message
        self._last_event_text = f"Sidecar 连接失败：{message[:80]}"
        self.statusChanged.emit()

    def _handle_raw_message(self, raw: str) -> None:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            self._last_event_text = "收到无法解析的 Sidecar 消息"
            self.statusChanged.emit()
            return

        event_type = payload.get("type", "")

        if event_type == "sidecar_connected":
            self._status_text = "Sidecar 已连接"
            self._last_event_text = payload.get("message", "Sidecar connected")
            self.statusChanged.emit()
            return

        if event_type == "sidecar_status":
            self._apply_status(payload)
            return

        if event_type == "notes_changed":
            reason = payload.get("reason", "changed")
            self._last_event_text = f"检测到便签变化：{reason}"
            self.statusChanged.emit()
            self.notesChanged.emit()
            return

        if event_type == "error":
            self._error_message = payload.get("message", "Sidecar error")
            self._last_event_text = self._error_message
            self.statusChanged.emit()
            return

        self._last_event_text = f"收到 Sidecar 事件：{event_type or 'unknown'}"
        self.statusChanged.emit()

    def _apply_status(self, payload: dict[str, Any]) -> None:
        notes_api = payload.get("notes_api", {}) or {}
        py_xiaozhi = payload.get("py_xiaozhi", {}) or {}

        notes_api_ok = bool(notes_api.get("ok"))
        root_exists = bool(py_xiaozhi.get("root_exists"))
        main_py_exists = bool(py_xiaozhi.get("main_py_exists"))
        notes_tool_installed = bool(py_xiaozhi.get("notes_tool_installed"))
        process_running = bool(py_xiaozhi.get("process_running"))

        self._notes_api_status_text = "Notes API 已连接" if notes_api_ok else "Notes API 未连接"
        self._py_xiaozhi_status_text = (
            "py-xiaozhi 运行中" if process_running else
            "py-xiaozhi 已配置" if root_exists and main_py_exists else
            "py-xiaozhi 未配置"
        )
        self._notes_tool_status_text = "notes 工具已安装" if notes_tool_installed else "notes 工具未安装"

        if self._connected and notes_api_ok and root_exists and main_py_exists and notes_tool_installed:
            self._assistant_status_text = "语音运行时已就绪" if process_running else "语音运行时未启动"
        elif self._connected:
            self._assistant_status_text = "语音运行时配置不完整"
        else:
            self._assistant_status_text = "语音助手未连接"

        self._status_text = "Sidecar 已连接" if self._connected else "Sidecar 未连接"
        self._error_message = "" if self._connected else self._error_message
        self.statusChanged.emit()
