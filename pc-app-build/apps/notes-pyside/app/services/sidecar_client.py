"""
WebSocket client for the PC Assistant Sidecar.

Phase 7.0.5:
- Voice UI uses authoritative runtime events, not log-watcher state guesses.
- Floating button restores click-to-abort while speaking.
- Stale listening/speaking/idle events are ignored around start/stop/abort.
- Runtime readiness can be proven by either process detection or PCBridge events.
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


TRUSTED_RUNTIME_SOURCES = {
    "py-xiaozhi.eventbus_bridge",
    "sidecar.runtime_manager",
}


class SidecarClient(QObject):
    connectedChanged = Signal()
    statusChanged = Signal()
    notesChanged = Signal()
    uiActionRequested = Signal(str, str)

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
        self._voice_button_state = "offline"

        self._notes_api_status_text = "Notes API 未确认"
        self._py_xiaozhi_status_text = "py-xiaozhi 未确认"
        self._py_xiaozhi_root_text = ""
        self._py_xiaozhi_python_text = ""
        self._py_xiaozhi_pids_text = ""
        self._py_xiaozhi_process_count = 0
        self._py_xiaozhi_launchable = False
        self._py_xiaozhi_running = False

        self._voice_runtime_ready = False
        self._last_voice_runtime_event_at = 0.0

        self._last_runtime_action_text = ""
        self._runtime_config_env_path = ""
        self._runtime_config_root_text = ""
        self._runtime_config_python_text = ""
        self._runtime_config_runtime_mode = "headless"
        self._runtime_config_start_mode = "minimized"
        self._runtime_config_window_mode = "minimized"
        self._runtime_config_auto_start = False
        self._last_runtime_config_text = ""
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
        self._outbox: queue.Queue[dict[str, Any]] = QueueType()

        self._pending_control = ""
        self._pending_control_since = 0.0
        self._last_command = ""
        self._last_command_at = 0.0

        self._developer_log_lines: list[str] = []
        self._runtime_timeline_started_at = 0.0
        self._runtime_timeline_label = ""

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

    @Property(str, notify=statusChanged)
    def voiceButtonState(self) -> str:
        return self._voice_button_state

    @Property(bool, notify=statusChanged)
    def isListening(self) -> bool:
        return self._voice_button_state == "listening"

    @Property(bool, notify=statusChanged)
    def isSpeaking(self) -> bool:
        return self._voice_button_state == "speaking"

    @Property(bool, notify=statusChanged)
    def voiceRuntimeReady(self) -> bool:
        return self._voice_runtime_ready

    @Property(str, notify=statusChanged)
    def notesApiStatusText(self) -> str:
        return self._notes_api_status_text

    @Property(str, notify=statusChanged)
    def pyXiaozhiStatusText(self) -> str:
        return self._py_xiaozhi_status_text

    @Property(str, notify=statusChanged)
    def pyXiaozhiRootText(self) -> str:
        return self._py_xiaozhi_root_text

    @Property(str, notify=statusChanged)
    def pyXiaozhiPythonText(self) -> str:
        return self._py_xiaozhi_python_text

    @Property(str, notify=statusChanged)
    def pyXiaozhiPidsText(self) -> str:
        return self._py_xiaozhi_pids_text

    @Property(int, notify=statusChanged)
    def pyXiaozhiProcessCount(self) -> int:
        return self._py_xiaozhi_process_count

    @Property(bool, notify=statusChanged)
    def pyXiaozhiLaunchable(self) -> bool:
        return self._py_xiaozhi_launchable

    @Property(bool, notify=statusChanged)
    def pyXiaozhiRunning(self) -> bool:
        return self._py_xiaozhi_running

    @Property(str, notify=statusChanged)
    def lastRuntimeActionText(self) -> str:
        return self._last_runtime_action_text

    @Property(str, notify=statusChanged)
    def runtimeConfigEnvPath(self) -> str:
        return self._runtime_config_env_path

    @Property(str, notify=statusChanged)
    def runtimeConfigRootText(self) -> str:
        return self._runtime_config_root_text or self._py_xiaozhi_root_text

    @Property(str, notify=statusChanged)
    def runtimeConfigPythonText(self) -> str:
        return self._runtime_config_python_text or self._py_xiaozhi_python_text

    @Property(str, notify=statusChanged)
    def runtimeConfigRuntimeMode(self) -> str:
        return self._runtime_config_runtime_mode

    @Property(str, notify=statusChanged)
    def runtimeConfigStartMode(self) -> str:
        return self._runtime_config_start_mode

    @Property(str, notify=statusChanged)
    def runtimeConfigWindowMode(self) -> str:
        return self._runtime_config_window_mode

    @Property(bool, notify=statusChanged)
    def runtimeConfigAutoStart(self) -> bool:
        return self._runtime_config_auto_start

    @Property(str, notify=statusChanged)
    def lastRuntimeConfigText(self) -> str:
        return self._last_runtime_config_text

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

    @Property(str, notify=statusChanged)
    def developerLogText(self) -> str:
        if not self._developer_log_lines:
            return "暂无开发者日志。点击设置页启动 py-xiaozhi 后，这里会记录从启动到空闲可用的时间线。"
        return "\n".join(self._developer_log_lines)

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
            return
        self._outbox.put({"type": "refresh_status"})

    @Slot()
    def refreshRuntimeConfig(self) -> None:
        if not self._connected:
            self.start()
            return
        self._outbox.put({"type": "get_runtime_config"})

    @Slot(str, str, str, str, str, bool)
    def savePyXiaozhiRuntimeConfig(self, root: str, python: str, runtime_mode: str, start_mode: str, window_mode: str, auto_start: bool) -> None:
        if not self._connected:
            self.start()

        payload = {
            "type": "save_runtime_config",
            "py_xiaozhi_root": root,
            "py_xiaozhi_python": python,
            "py_xiaozhi_runtime_mode": runtime_mode,
            "py_xiaozhi_start_mode": start_mode,
            "py_xiaozhi_window_mode": window_mode,
            "py_xiaozhi_auto_start": bool(auto_start),
        }
        self._outbox.put(payload)
        self._last_runtime_config_text = "正在保存 py-xiaozhi 运行时配置"
        self._last_event_text = self._last_runtime_config_text
        self.statusChanged.emit()

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

        self._note_command("start_listen")
        self._set_pending("start_listen")
        self._voice_button_state = "starting"
        self._assistant_status_text = "正在请求开始聆听"
        self._queue_control("start_listen", mode="manual")

    @Slot(str)
    def startListenMode(self, mode: str) -> None:
        if not self._can_control_voice():
            self._show_runtime_not_ready()
            return

        self._note_command("start_listen")
        self._set_pending("start_listen")
        self._voice_button_state = "starting"
        self._assistant_status_text = "正在请求开始聆听"
        self._queue_control("start_listen", mode=mode or "manual")

    @Slot()
    def stopListen(self) -> None:
        if not self._can_control_voice():
            self._show_runtime_not_ready()
            return

        self._note_command("stop_listen")
        self._set_pending("stop_listen")
        self._voice_button_state = "stopping"
        self._assistant_status_text = "正在请求停止聆听"
        self._queue_control("stop_listen")

    @Slot()
    def toggleListen(self) -> None:
        if not self._can_control_voice():
            self._show_runtime_not_ready()
            return

        if self._voice_button_state in {"starting", "listening"}:
            self.stopListen()
        elif self._voice_button_state == "speaking":
            self.abortSpeaking()
        else:
            self.startListen()

    @Slot()
    def abortSpeaking(self) -> None:
        if not self._can_control_voice():
            self._show_runtime_not_ready()
            return

        self._note_command("abort")
        self._set_pending("abort")
        self._voice_button_state = "aborting"
        self._assistant_status_text = "正在请求打断"
        self._queue_control("abort")

    @Slot()
    def startPyXiaozhi(self) -> None:
        self._begin_runtime_timeline("start_py_xiaozhi")
        self._queue_runtime_action("start_py_xiaozhi")

    @Slot()
    def stopPyXiaozhi(self) -> None:
        self._set_runtime_offline()
        self._queue_runtime_action("stop_py_xiaozhi")

    @Slot()
    def restartPyXiaozhi(self) -> None:
        self._set_runtime_offline()
        self._queue_runtime_action("restart_py_xiaozhi")

    def _can_control_voice(self) -> bool:
        return self._connected and self._voice_runtime_ready

    def _show_runtime_not_ready(self) -> None:
        self._voice_button_state = "offline"
        self._assistant_state = "offline"
        self._assistant_status_text = "语音助手未启动，请先在设置页启动"
        self._last_control_text = "语音助手未启动，右下角按钮不可控制运行时"
        self._last_event_text = self._last_control_text
        self._pending_control = ""
        self.statusChanged.emit()

    def _mark_voice_runtime_ready(self) -> None:
        was_ready = self._voice_runtime_ready
        self._voice_runtime_ready = True
        self._last_voice_runtime_event_at = time.time()
        if not was_ready:
            self._append_developer_log("RUNTIME_READY voice runtime became ready")
        if self._voice_button_state == "offline":
            self._voice_button_state = "idle"
        if self._assistant_state == "offline":
            self._assistant_state = "idle"
        if self._assistant_status_text in {"语音助手未连接", "语音助手未启动", "语音助手未启动，请先在设置页启动"}:
            self._assistant_status_text = "语音运行时已就绪"

    def _note_command(self, command: str) -> None:
        self._last_command = command
        self._last_command_at = time.time()

    def _recent_command(self, command: str, seconds: float = 4.0) -> bool:
        return self._last_command == command and (time.time() - self._last_command_at) <= seconds

    def _set_pending(self, command: str) -> None:
        self._pending_control = command
        self._pending_control_since = time.time()

    def _clear_pending(self) -> None:
        self._pending_control = ""
        self._pending_control_since = 0.0

    def _set_runtime_offline(self) -> None:
        self._py_xiaozhi_running = False
        self._voice_runtime_ready = False
        self._last_voice_runtime_event_at = 0.0
        self._py_xiaozhi_process_count = 0
        self._py_xiaozhi_pids_text = ""
        self._voice_button_state = "offline"
        self._assistant_state = "offline"
        self._assistant_status_text = "语音助手未启动"
        self._clear_pending()

    def _queue_runtime_action(self, action_type: str) -> None:
        if not self._connected:
            self.start()

        self._outbox.put({
            "type": action_type,
            "request_id": f"pc-app-runtime-{int(time.time() * 1000)}",
        })
        self._append_developer_log(f"APP_ACTION {action_type}")
        self._last_runtime_action_text = f"已发送 py-xiaozhi 运行时操作：{action_type}"
        self._last_event_text = self._last_runtime_action_text
        self.statusChanged.emit()

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
                    await websocket.send(json.dumps({"type": "get_runtime_config"}, ensure_ascii=False))
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
            if self._voice_runtime_ready and self._voice_button_state == "offline":
                self._voice_button_state = "idle"
            self._error_message = ""
        else:
            self._status_text = "Sidecar 未连接"
            self._assistant_status_text = "语音助手未连接"
            self._voice_button_state = "offline"
            self._assistant_state = "offline"
            self._voice_runtime_ready = False
            self._clear_pending()

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

        event_type = str(payload.get("type", ""))
        source = str(payload.get("source", ""))
        self._append_event_to_developer_log(payload)

        if event_type == "sidecar_connected":
            self._status_text = "Sidecar 已连接"
            self._last_event_text = payload.get("message", "Sidecar connected")
            self.statusChanged.emit()
            return

        if event_type == "runtime_config":
            self._apply_runtime_config(payload)
            return

        if event_type == "runtime_config_saved":
            self._last_runtime_config_text = payload.get("message", "py-xiaozhi 运行时配置已保存")
            self._last_event_text = self._last_runtime_config_text
            config_payload = payload.get("config", {}) or {}
            if isinstance(config_payload, dict):
                self._apply_runtime_config(config_payload)
            self.statusChanged.emit()
            return

        if event_type == "sidecar_status":
            runtime_config = payload.get("runtime_config", {}) or {}
            if isinstance(runtime_config, dict):
                self._apply_runtime_config(runtime_config)
            self._apply_status(payload)
            return

        if event_type == "sidecar_events":
            items = payload.get("items", []) or []
            if items:
                self._apply_recent_event(items[-1])
            return

        if event_type == "ui_action":
            self._handle_ui_action(payload)
            return

        if event_type == "control_accepted":
            self._last_control_text = payload.get("message", "语音控制命令已被 Sidecar 接收")
            self._last_event_text = self._last_control_text
            self.statusChanged.emit()
            return

        if event_type in {"assistant_control", "assistant_control_received"}:
            self._mark_voice_runtime_ready()
            self._last_control_text = payload.get("message", "语音控制事件")
            self._last_event_text = self._last_control_text
            self.statusChanged.emit()
            return

        if event_type == "assistant_control_result":
            self._mark_voice_runtime_ready()
            self._apply_control_result(payload)
            return

        if event_type == "assistant_control_error":
            self._mark_voice_runtime_ready()
            self._error_message = payload.get("message", "语音控制命令执行失败")
            self._last_control_text = self._error_message
            self._last_event_text = self._error_message
            self._voice_button_state = "idle"
            self._assistant_status_text = "语音运行时已就绪"
            self._clear_pending()
            self.statusChanged.emit()
            return

        if event_type == "runtime_action_accepted":
            self._last_runtime_action_text = payload.get("message", "py-xiaozhi 运行时操作已接收")
            self._last_event_text = self._last_runtime_action_text
            self.statusChanged.emit()
            return

        if event_type == "runtime_action_result":
            self._last_runtime_action_text = payload.get("message", "py-xiaozhi 运行时操作完成")
            self._last_event_text = self._last_runtime_action_text
            data = payload.get("data", {}) or {}
            status = data.get("status", {}) or {}
            if status:
                self._append_developer_log(
                    "RUNTIME_STATUS "
                    + f"running={bool(status.get('process_running'))} "
                    + f"pids={status.get('process_pids', [])} "
                    + f"mode={status.get('runtime_mode', '')}"
                )
                self._apply_py_xiaozhi_status(status)
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
            if self._is_authoritative_source(source):
                self._mark_voice_runtime_ready()
            self._last_transcript_text = payload.get("text", "")
            self._last_event_text = payload.get("message", "收到语音识别文本")
            self.statusChanged.emit()
            return

        if event_type == "assistant_reply":
            if self._is_authoritative_source(source):
                self._mark_voice_runtime_ready()
            self._last_assistant_reply_text = payload.get("text", "")
            self._last_event_text = payload.get("message", "收到助手回复")
            self.statusChanged.emit()
            return

        if event_type == "audio_channel":
            if self._is_authoritative_source(source):
                self._mark_voice_runtime_ready()
            self._last_audio_channel_text = payload.get("message", payload.get("state", ""))
            self._last_event_text = self._last_audio_channel_text
            self.statusChanged.emit()
            return

        if event_type == "runtime_error":
            if self._is_authoritative_source(source):
                self._mark_voice_runtime_ready()
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


    def _begin_runtime_timeline(self, label: str) -> None:
        self._runtime_timeline_started_at = time.time()
        self._runtime_timeline_label = label
        self._developer_log_lines.clear()
        self._append_developer_log(f"TIMELINE_START {label}")

    def _elapsed_ms(self) -> str:
        if not self._runtime_timeline_started_at:
            return "-"
        return f"{int((time.time() - self._runtime_timeline_started_at) * 1000)}ms"

    def _append_developer_log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        elapsed = self._elapsed_ms()
        line = f"{timestamp} +{elapsed} {message}" if elapsed != "-" else f"{timestamp} {message}"
        self._developer_log_lines.append(line)
        if len(self._developer_log_lines) > 500:
            self._developer_log_lines = self._developer_log_lines[-500:]

    def _append_event_to_developer_log(self, payload: dict[str, Any]) -> None:
        event_type = str(payload.get("type", ""))
        source = str(payload.get("source", ""))
        message = str(payload.get("message", "") or payload.get("status", "") or payload.get("state", ""))
        command = str(payload.get("command", "") or "")
        action = str(payload.get("action", "") or "")
        parts = [f"EVENT {event_type}"]
        if source:
            parts.append(f"source={source}")
        if command:
            parts.append(f"command={command}")
        if action:
            parts.append(f"action={action}")
        if message:
            parts.append(message[:120])
        self._append_developer_log(" | ".join(parts))

    def _is_authoritative_source(self, source: str) -> bool:
        return source in TRUSTED_RUNTIME_SOURCES or source.startswith("py-xiaozhi.eventbus_bridge")

    def _apply_control_result(self, payload: dict[str, Any]) -> None:
        command = str(payload.get("command") or payload.get("data", {}).get("command") or "")
        self._last_control_text = payload.get("message", "语音控制命令已执行")
        self._last_event_text = self._last_control_text

        if command == "start_listen":
            self._voice_button_state = "listening"
            self._assistant_state = "listening"
            self._assistant_status_text = "语音助手正在聆听"
        elif command in {"stop_listen", "abort", "abort_speaking"}:
            self._voice_button_state = "idle"
            self._assistant_state = "idle"
            self._assistant_status_text = "语音助手空闲"
        self._clear_pending()
        self.statusChanged.emit()

    def _handle_assistant_state(self, payload: dict[str, Any]) -> None:
        source = str(payload.get("source", ""))
        text = str(payload.get("message") or payload.get("status") or payload.get("state") or "语音助手状态更新")
        status = str(payload.get("status") or payload.get("state") or "").lower()

        # Log watcher state is not authoritative. It is useful for diagnostics only.
        if not self._is_authoritative_source(source):
            self._last_runtime_state_text = text
            self._last_event_text = text
            self.statusChanged.emit()
            return

        self._mark_voice_runtime_ready()

        if "播报结束" in text or "语音播报结束" in text:
            status = "idle"

        if status in {"connected", "stopped", "emotion", "tooling", "manual_toggle", "aborted"}:
            self._last_runtime_state_text = text
            self._last_event_text = text
            self.statusChanged.emit()
            return

        if status not in {"idle", "listening", "speaking"}:
            self._last_runtime_state_text = text
            self._last_event_text = text
            self.statusChanged.emit()
            return

        if self._should_ignore_state(status):
            self._last_runtime_state_text = text
            self._last_event_text = text
            self.statusChanged.emit()
            return

        mapping = {
            "idle": "语音助手空闲",
            "listening": "语音助手正在聆听",
            "speaking": "语音助手正在播报",
        }
        self._assistant_state = status
        self._assistant_status_text = mapping.get(status, self._assistant_status_text)

        if status == "idle":
            self._voice_button_state = "idle"
            self._clear_pending()
        elif status == "listening":
            self._voice_button_state = "listening"
            if self._pending_control == "start_listen":
                self._clear_pending()
        elif status == "speaking":
            self._voice_button_state = "speaking"
            if self._pending_control == "start_listen":
                self._clear_pending()

        self._last_runtime_state_text = text
        self._last_event_text = text
        self.statusChanged.emit()

    def _should_ignore_state(self, status: str) -> bool:
        # After an explicit stop/abort, late listening/speaking events are stale.
        if self._recent_command("stop_listen") and status == "listening":
            return True
        if self._recent_command("abort") and status == "speaking":
            return True
        # During start, py-xiaozhi may briefly report idle before listening.
        if self._recent_command("start_listen") and status == "idle" and self._voice_button_state == "starting":
            return True
        return False

    def _apply_recent_event(self, event: dict[str, Any]) -> None:
        # Recent events are history, not live button input.
        self._last_event_text = event.get("message") or f"历史事件：{event.get('type', 'unknown')}"
        self.statusChanged.emit()

    def _handle_ui_action(self, payload: dict[str, Any]) -> None:
        action = str(payload.get("action", "") or "").strip()
        data = payload.get("data", {}) or {}
        message = payload.get("message") or f"请求界面执行：{action or 'unknown'}"

        if not isinstance(data, dict):
            data = {"value": data}

        if action:
            try:
                data_json = json.dumps(data, ensure_ascii=False)
            except Exception:
                data_json = "{}"
            self.uiActionRequested.emit(action, data_json)

        self._last_event_text = message
        self.statusChanged.emit()

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

        ui_action = payload.get("ui_action")
        if isinstance(ui_action, dict):
            self._handle_ui_action({
                "type": "ui_action",
                "action": ui_action.get("action", ""),
                "data": ui_action.get("data", {}) or {},
                "message": ui_action.get("message", message),
            })

        self.statusChanged.emit()

        if bool(payload.get("note_changed")):
            self.notesChanged.emit()

    def _apply_runtime_config(self, payload: dict[str, Any]) -> None:
        settings = payload.get("settings", {}) or {}
        self._runtime_config_env_path = str(payload.get("env_path") or self._runtime_config_env_path or "")
        self._runtime_config_root_text = str(settings.get("py_xiaozhi_root") or self._runtime_config_root_text or "")
        self._runtime_config_python_text = str(settings.get("py_xiaozhi_python") or self._runtime_config_python_text or "")
        self._runtime_config_runtime_mode = str(settings.get("py_xiaozhi_runtime_mode") or self._runtime_config_runtime_mode or "headless")
        self._runtime_config_start_mode = str(settings.get("py_xiaozhi_start_mode") or self._runtime_config_start_mode or "minimized")
        self._runtime_config_window_mode = str(settings.get("py_xiaozhi_window_mode") or self._runtime_config_window_mode or "minimized")
        self._runtime_config_auto_start = bool(settings.get("py_xiaozhi_auto_start", self._runtime_config_auto_start))
        if not self._last_runtime_config_text:
            self._last_runtime_config_text = "py-xiaozhi 运行时配置已加载"
        self.statusChanged.emit()

    def _apply_py_xiaozhi_status(self, py_xiaozhi: dict[str, Any]) -> None:
        root_exists = bool(py_xiaozhi.get("root_exists"))
        main_py_exists = bool(py_xiaozhi.get("main_py_exists"))
        notes_tool_installed = bool(py_xiaozhi.get("notes_tool_installed"))
        process_running = bool(py_xiaozhi.get("process_running"))
        process_count = int(py_xiaozhi.get("process_count") or 0)
        process_pids = py_xiaozhi.get("process_pids") or []

        self._py_xiaozhi_running = process_running
        self._py_xiaozhi_process_count = process_count
        self._py_xiaozhi_launchable = bool(py_xiaozhi.get("launchable"))
        self._py_xiaozhi_root_text = str(py_xiaozhi.get("root") or "")
        self._py_xiaozhi_python_text = str(py_xiaozhi.get("python") or "")
        self._py_xiaozhi_pids_text = ", ".join([str(pid) for pid in process_pids]) if process_pids else ""

        if process_running:
            self._voice_runtime_ready = True
            self._last_voice_runtime_event_at = time.time()
        else:
            # When no process is detected, do not keep an old bridge-ready state forever.
            # This prevents the voice button from staying in "正在启动" after a failed start
            # or a fixed process detector reporting the runtime as stopped.
            age = time.time() - self._last_voice_runtime_event_at if self._last_voice_runtime_event_at else 9999.0
            if age > 8.0:
                self._voice_runtime_ready = False

        bridge_ok = bool(py_xiaozhi.get("pc_bridge_installed"))
        bridge_text = "bridge 已安装" if bridge_ok else "bridge 未安装"

        if process_running:
            self._py_xiaozhi_status_text = f"py-xiaozhi 运行中（{process_count} 个进程）"
        elif self._voice_runtime_ready:
            self._py_xiaozhi_status_text = "py-xiaozhi 语音桥接在线（进程检测未命中）"
        elif root_exists and main_py_exists:
            self._py_xiaozhi_status_text = "py-xiaozhi 已配置，未运行"
        else:
            self._py_xiaozhi_status_text = "py-xiaozhi 未配置"

        self._notes_tool_status_text = (
            ("notes 工具已安装" if notes_tool_installed else "notes 工具未安装")
            + " · "
            + bridge_text
        )

        if not process_running and not self._voice_runtime_ready:
            self._voice_button_state = "offline"
            self._assistant_state = "offline"
            self._assistant_status_text = "语音助手未启动"
            self._clear_pending()
        elif self._voice_runtime_ready and self._voice_button_state == "offline":
            self._voice_button_state = "idle"
            if self._assistant_state == "offline":
                self._assistant_state = "idle"
            self._assistant_status_text = "语音运行时已就绪"

    def _apply_status(self, payload: dict[str, Any]) -> None:
        notes_api = payload.get("notes_api", {}) or {}
        py_xiaozhi = payload.get("py_xiaozhi", {}) or {}

        notes_api_ok = bool(notes_api.get("ok"))
        root_exists = bool(py_xiaozhi.get("root_exists"))
        main_py_exists = bool(py_xiaozhi.get("main_py_exists"))
        notes_tool_installed = bool(py_xiaozhi.get("notes_tool_installed"))

        self._notes_api_status_text = "Notes API 已连接" if notes_api_ok else "Notes API 未连接"
        self._apply_py_xiaozhi_status(py_xiaozhi)

        if self._connected and notes_api_ok and root_exists and main_py_exists and notes_tool_installed and self._voice_runtime_ready:
            if self._voice_button_state == "offline":
                self._voice_button_state = "idle"
            if self._assistant_state == "offline":
                self._assistant_state = "idle"
            if self._assistant_status_text in {"语音助手未连接", "语音助手未启动"}:
                self._assistant_status_text = "语音运行时已就绪"
        elif self._connected and not self._voice_runtime_ready:
            self._assistant_status_text = "语音助手未启动"
            self._voice_button_state = "offline"
            self._assistant_state = "offline"
        elif self._connected:
            self._assistant_status_text = "语音运行时配置不完整"
        else:
            self._assistant_status_text = "语音助手未连接"
            self._voice_button_state = "offline"
            self._assistant_state = "offline"

        self._status_text = "Sidecar 已连接" if self._connected else "Sidecar 未连接"
        self._error_message = "" if self._connected else self._error_message
        self.statusChanged.emit()


class QueueType(queue.Queue):
    """Named alias to keep the type obvious in stack traces."""
