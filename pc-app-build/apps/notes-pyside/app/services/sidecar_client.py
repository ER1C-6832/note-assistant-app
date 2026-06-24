"""
WebSocket client for the PC Assistant Sidecar.

Phase 6.1.1 hotfix:
- Avoid blocking Queue.get through asyncio.to_thread in the sender task.
- The previous implementation could leave a worker thread blocked after the
  PySide window closed, causing start_pc_app.bat to hang instead of returning.
"""

from __future__ import annotations

import asyncio
import json
import os
import queue
import threading
import time
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
        self._assistant_state = "offline"
        self._notes_api_status_text = "Notes API 未确认"
        self._py_xiaozhi_status_text = "py-xiaozhi 未确认"
        self._notes_tool_status_text = "notes 工具未确认"
        self._last_event_text = ""
        self._last_tool_event_text = ""
        self._last_tool_result_text = ""
        self._last_tool_name = ""
        self._last_tool_status = ""
        self._last_transcript_text = ""
        self._last_assistant_reply_text = ""
        self._last_runtime_log_text = ""
        self._last_runtime_state_text = ""
        self._last_audio_channel_text = ""
        self._last_control_text = ""
        self._error_message = ""
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._outbox: queue.Queue[dict[str, Any]] = queue.Queue()

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
    def assistantState(self) -> str:
        return self._assistant_state

    @Property(bool, notify=statusChanged)
    def isListening(self) -> bool:
        return self._assistant_state == "listening"

    @Property(bool, notify=statusChanged)
    def isSpeaking(self) -> bool:
        return self._assistant_state == "speaking"

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
    def lastToolEventText(self) -> str:
        return self._last_tool_event_text

    @Property(str, notify=statusChanged)
    def lastToolResultText(self) -> str:
        return self._last_tool_result_text

    @Property(str, notify=statusChanged)
    def lastToolName(self) -> str:
        return self._last_tool_name

    @Property(str, notify=statusChanged)
    def lastToolStatus(self) -> str:
        return self._last_tool_status

    @Property(str, notify=statusChanged)
    def lastTranscriptText(self) -> str:
        return self._last_transcript_text

    @Property(str, notify=statusChanged)
    def lastAssistantReplyText(self) -> str:
        return self._last_assistant_reply_text

    @Property(str, notify=statusChanged)
    def lastRuntimeLogText(self) -> str:
        return self._last_runtime_log_text

    @Property(str, notify=statusChanged)
    def lastRuntimeStateText(self) -> str:
        return self._last_runtime_state_text

    @Property(str, notify=statusChanged)
    def lastAudioChannelText(self) -> str:
        return self._last_audio_channel_text

    @Property(str, notify=statusChanged)
    def lastControlText(self) -> str:
        return self._last_control_text

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
        try:
            self._outbox.put_nowait({"type": "__stop__"})
        except Exception:
            pass

    @Slot()
    def refreshStatus(self) -> None:
        if not self._connected:
            self.start()

    @Slot()
    def startListen(self) -> None:
        if self._assistant_state == "listening":
            self._last_control_text = "已经在聆听中"
            self._last_event_text = self._last_control_text
            self.statusChanged.emit()
            return

        self._assistant_state = "starting"
        self._assistant_status_text = "正在请求开始聆听"
        self._queue_control("start_listen", mode="manual")

    @Slot(str)
    def startListenMode(self, mode: str) -> None:
        if self._assistant_state == "listening":
            self._last_control_text = "已经在聆听中"
            self._last_event_text = self._last_control_text
            self.statusChanged.emit()
            return

        self._assistant_state = "starting"
        self._assistant_status_text = "正在请求开始聆听"
        self._queue_control("start_listen", mode=mode or "manual")

    @Slot()
    def stopListen(self) -> None:
        if self._assistant_state in {"idle", "offline", "stopping"}:
            self._last_control_text = "当前没有正在进行的聆听"
            self._last_event_text = self._last_control_text
            self.statusChanged.emit()
            return

        self._assistant_state = "stopping"
        self._assistant_status_text = "正在请求停止聆听"
        self._queue_control("stop_listen")

    @Slot()
    def toggleListen(self) -> None:
        if self._assistant_state in {"listening", "starting"}:
            self.stopListen()
        elif self._assistant_state == "speaking":
            self.abortSpeaking()
        else:
            self.startListen()

    @Slot()
    def abortSpeaking(self) -> None:
        self._assistant_state = "aborting"
        self._assistant_status_text = "正在请求打断"
        self._queue_control("abort")

    def _queue_control(self, command_type: str, **payload: Any) -> None:
        if not self._connected:
            self.start()

        message = {
            "type": command_type,
            "request_id": f"pc-app-{int(time.time() * 1000)}",
        }
        message.update(payload)

        self._outbox.put(message)
        self._last_control_text = f"已发送语音控制命令：{command_type}"
        self._last_event_text = self._last_control_text
        self.statusChanged.emit()

    def _run_thread(self) -> None:
        asyncio.run(self._connection_loop())

    async def _connection_loop(self) -> None:
        while not self._stop_event.is_set():
            sender_task = None
            try:
                async with websockets.connect(
                    self._ws_url,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=2,
                ) as websocket:
                    self._connection_changed.emit(True)
                    await websocket.send(json.dumps({"type": "refresh_status"}, ensure_ascii=False))
                    await websocket.send(json.dumps({"type": "refresh_events"}, ensure_ascii=False))

                    sender_task = asyncio.create_task(self._sender_loop(websocket))

                    async for message in websocket:
                        if self._stop_event.is_set():
                            break
                        self._raw_message_received.emit(str(message))
            except Exception as exc:
                if not self._stop_event.is_set():
                    self._connection_changed.emit(False)
                    self._error_received.emit(str(exc))
            finally:
                if sender_task:
                    sender_task.cancel()
                    try:
                        await sender_task
                    except asyncio.CancelledError:
                        pass
                    except Exception:
                        pass

            if not self._stop_event.is_set():
                await asyncio.sleep(3)

        self._connection_changed.emit(False)

    async def _sender_loop(self, websocket) -> None:
        while not self._stop_event.is_set():
            try:
                message = self._outbox.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.08)
                continue

            if message.get("type") == "__stop__":
                break

            await websocket.send(json.dumps(message, ensure_ascii=False))

    def _set_connected(self, connected: bool) -> None:
        if self._connected == connected:
            return

        self._connected = connected

        if connected:
            self._status_text = "Sidecar 已连接"
            self._assistant_status_text = "语音运行时检测中"
            if self._assistant_state == "offline":
                self._assistant_state = "idle"
            self._error_message = ""
        else:
            self._status_text = "Sidecar 未连接"
            self._assistant_status_text = "语音助手未连接"
            self._assistant_state = "offline"

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

        if event_type == "sidecar_events":
            items = payload.get("items", []) or []
            if items:
                self._apply_recent_event(items[-1])
            return

        if event_type == "control_accepted":
            self._last_control_text = payload.get("message", "语音控制命令已被 Sidecar 接收")
            self._last_event_text = self._last_control_text
            self.statusChanged.emit()
            return

        if event_type in {"assistant_control", "assistant_control_received"}:
            self._last_control_text = payload.get("message", "语音控制事件")
            self._last_event_text = self._last_control_text
            self.statusChanged.emit()
            return

        if event_type == "assistant_control_result":
            self._last_control_text = payload.get("message", "语音控制命令已执行")
            self._last_event_text = self._last_control_text
            if self._assistant_state in {"starting", "stopping", "aborting"}:
                self._assistant_state = "idle" if self._assistant_state != "starting" else self._assistant_state
            self.statusChanged.emit()
            return

        if event_type == "assistant_control_error":
            self._error_message = payload.get("message", "语音控制命令执行失败")
            self._last_control_text = self._error_message
            self._last_event_text = self._error_message
            if self._assistant_state in {"starting", "stopping", "aborting"}:
                self._assistant_state = "idle"
                self._assistant_status_text = "语音运行时已就绪"
            self.statusChanged.emit()
            return

        if event_type == "notes_changed":
            reason = payload.get("reason", "changed")
            self._last_event_text = f"检测到便签变化：{reason}"
            self.statusChanged.emit()
            self.notesChanged.emit()
            return

        if event_type == "tool_call":
            self._handle_tool_call(payload)
            return

        if event_type == "tool_result":
            self._handle_tool_result(payload)
            return

        if event_type in {"assistant_status", "assistant_state"}:
            self._handle_assistant_state(payload)
            return

        if event_type == "assistant_transcript":
            self._last_transcript_text = payload.get("text", "")
            self._last_event_text = payload.get("message", "收到语音识别文本")
            self.statusChanged.emit()
            return

        if event_type == "assistant_reply":
            self._last_assistant_reply_text = payload.get("text", "")
            self._last_event_text = payload.get("message", "收到助手回复")
            self.statusChanged.emit()
            return

        if event_type == "audio_channel":
            self._last_audio_channel_text = payload.get("message", payload.get("state", ""))
            self._last_event_text = self._last_audio_channel_text
            self.statusChanged.emit()
            return

        if event_type == "runtime_error":
            self._error_message = payload.get("message", "py-xiaozhi runtime error")
            self._last_event_text = self._error_message
            self.statusChanged.emit()
            return

        if event_type == "assistant_log":
            self._last_runtime_log_text = payload.get("message", payload.get("raw", ""))
            self._last_event_text = self._last_runtime_log_text
            self.statusChanged.emit()
            return

        if event_type == "error":
            self._error_message = payload.get("message", "Sidecar error")
            self._last_event_text = self._error_message
            self.statusChanged.emit()
            return

        self._last_event_text = f"收到 Sidecar 事件：{event_type or 'unknown'}"
        self.statusChanged.emit()

    def _handle_assistant_state(self, payload: dict[str, Any]) -> None:
        text = payload.get("message") or payload.get("status") or payload.get("state") or "语音助手状态更新"
        status = str(payload.get("status") or payload.get("state") or "").lower()

        if status in {"idle", "listening", "speaking", "connected", "stopped"}:
            mapping = {
                "idle": "语音助手空闲",
                "listening": "语音助手正在聆听",
                "speaking": "语音助手正在播报",
                "connected": "语音运行时已连接",
                "stopped": "语音运行时已停止",
            }
            self._assistant_state = "idle" if status in {"connected", "stopped"} else status
            self._assistant_status_text = mapping.get(status, self._assistant_status_text)

        self._last_runtime_state_text = str(text)
        self._last_event_text = str(text)
        self.statusChanged.emit()

    def _apply_recent_event(self, event: dict[str, Any]) -> None:
        self._handle_raw_message(json.dumps(event, ensure_ascii=False))

    def _handle_tool_call(self, payload: dict[str, Any]) -> None:
        tool_name = payload.get("tool_name", "unknown")
        message = payload.get("message") or f"开始调用 {tool_name}"
        self._last_tool_name = tool_name
        self._last_tool_status = "运行中"
        self._last_tool_event_text = message
        self._last_event_text = message
        self.statusChanged.emit()

    def _handle_tool_result(self, payload: dict[str, Any]) -> None:
        tool_name = payload.get("tool_name", "unknown")
        status = payload.get("status", "")
        message = payload.get("message") or f"{tool_name} 执行完成"
        self._last_tool_name = tool_name
        self._last_tool_status = "成功" if status == "success" else "失败" if status == "error" else str(status)
        self._last_tool_result_text = message
        self._last_event_text = message
        self.statusChanged.emit()

        if bool(payload.get("note_changed")):
            self.notesChanged.emit()

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
            if self._assistant_state in {"offline", ""}:
                self._assistant_state = "idle"
        elif self._connected:
            self._assistant_status_text = "语音运行时配置不完整"
        else:
            self._assistant_status_text = "语音助手未连接"
            self._assistant_state = "offline"

        self._status_text = "Sidecar 已连接" if self._connected else "Sidecar 未连接"
        self._error_message = "" if self._connected else self._error_message
        self.statusChanged.emit()
