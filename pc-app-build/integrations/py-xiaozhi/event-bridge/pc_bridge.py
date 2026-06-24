from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.logging import get_logger
from src.plugins.base import Plugin

logger = get_logger()


class PCBridgePlugin(Plugin):
    """
    PC Assistant Bridge plugin.

    Phase 7.0.5:
    - Emits authoritative assistant_state after App control commands.
    - Emits idle on TTS stop instead of a possibly stale snapshot.
    - Keeps /api/control polling so the PC App can start/stop/abort listening.
    """

    name = "pc_bridge"
    priority = 65

    def __init__(self) -> None:
        super().__init__()
        self.enabled = os.getenv("PC_BRIDGE_ENABLED", "1").strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
        }
        self.event_url = os.getenv(
            "SIDECAR_EVENT_URL",
            "http://127.0.0.1:17891/api/events",
        )
        self.control_url = os.getenv(
            "SIDECAR_CONTROL_URL",
            "http://127.0.0.1:17891/api/control",
        )
        self.control_poll_seconds = float(os.getenv("PC_BRIDGE_CONTROL_POLL_SECONDS", "0.35"))
        self.emit_debug_json = os.getenv(
            "PC_BRIDGE_DEBUG_JSON",
            "0",
        ).strip().lower() in {"1", "true", "yes", "on"}
        self._registered_handlers: list[tuple[str, Any]] = []
        self._last_status = ""
        self._last_command_id = 0
        self._control_task = None

    async def setup(self, ctx, cmd) -> None:
        await super().setup(ctx, cmd)

    async def start(self) -> None:
        if not self.enabled:
            logger.info("PCBridgePlugin disabled by PC_BRIDGE_ENABLED=0")
            return

        from src.core.event_bus import Events

        subscriptions = [
            (Events.AUDIO_CHANNEL_OPENED, self._on_audio_channel_opened),
            (Events.AUDIO_CHANNEL_CLOSED, self._on_audio_channel_closed),
            (Events.NETWORK_ERROR, self._on_network_error),
            (Events.UI_SEND_TEXT, self._on_ui_send_text),
            (Events.UI_BUTTON_PRESS, self._on_ui_listen_start),
            (Events.UI_AUTO_START, self._on_ui_listen_start),
            (Events.UI_MANUAL_TOGGLE, self._on_ui_manual_toggle),
            (Events.UI_ABORT_REQUEST, self._on_ui_abort),
        ]

        for event_name, handler in subscriptions:
            self._ctx.event_bus.on(event_name, handler)
            self._registered_handlers.append((event_name, handler))

        try:
            self._control_task = self._cmd.spawn(
                self._control_loop(),
                name="pc_bridge:control_loop",
            )
        except Exception:
            self._control_task = asyncio.create_task(self._control_loop())

        logger.info("PCBridgePlugin started, forwarding events to %s", self.event_url)
        logger.info("PCBridgePlugin polling controls from %s", self.control_url)

        status = self._snapshot_status()
        await self._emit_state(
            status if status in {"idle", "listening", "speaking"} else "idle",
            "PC Bridge 已连接 py-xiaozhi EventBus，并已启用 App 语音控制",
        )

    async def stop(self) -> None:
        if not self.enabled:
            return

        try:
            for event_name, handler in self._registered_handlers:
                self._ctx.event_bus.off(event_name, handler)
            self._registered_handlers.clear()
        except Exception:
            pass

        if self._control_task:
            try:
                self._control_task.cancel()
            except Exception:
                pass

        await self._emit_state("idle", "PC Bridge 已停止")

    async def _control_loop(self) -> None:
        while self.enabled:
            try:
                commands = await asyncio.to_thread(self._fetch_controls, self._last_command_id)
                for command in commands:
                    command_id = int(command.get("command_id", 0))
                    if command_id <= self._last_command_id:
                        continue

                    self._last_command_id = command_id
                    await self._execute_control(command)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.debug("PCBridgePlugin control polling failed", exc_info=True)

            await asyncio.sleep(self.control_poll_seconds)

    def _fetch_controls(self, after: int) -> list[dict[str, Any]]:
        qs = urlencode({"after": int(after or 0), "limit": 20})
        url = f"{self.control_url}?{qs}"

        with urlopen(url, timeout=0.8) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))

        items = payload.get("items", [])
        return items if isinstance(items, list) else []

    async def _execute_control(self, command: dict[str, Any]) -> None:
        command_name = str(command.get("command", "")).strip()
        mode = str(command.get("mode", "manual") or "manual").strip().lower()

        await self._emit({
            "type": "assistant_control_received",
            "command": command_name,
            "command_id": command.get("command_id"),
            "message": f"py-xiaozhi 收到 App 语音控制命令：{command_name}",
            "data": command,
        })

        try:
            if command_name == "start_listen":
                await self._start_listening(mode)
                await self._emit_state("listening", "语音助手正在聆听", command=command)
            elif command_name == "stop_listen":
                await self._cmd.stop_listening()
                await self._emit_state("idle", "语音助手空闲", command=command)
            elif command_name == "toggle_listen":
                if self._ctx.is_listening():
                    await self._cmd.stop_listening()
                    await self._emit_state("idle", "语音助手空闲", command=command)
                else:
                    await self._start_listening(mode)
                    await self._emit_state("listening", "语音助手正在聆听", command=command)
            elif command_name in {"abort", "abort_speaking"}:
                from src.constants.constants import AbortReason

                await self._cmd.abort_speaking(AbortReason.USER_INTERRUPTION)
                await self._emit_state("idle", "语音助手空闲", command=command)
            else:
                await self._emit({
                    "type": "assistant_control_error",
                    "command": command_name,
                    "message": f"未知语音控制命令：{command_name}",
                    "data": command,
                })
                return

            await self._emit({
                "type": "assistant_control_result",
                "command": command_name,
                "status": "success",
                "message": f"语音控制命令已执行：{command_name}",
                "runtime_state": self._state_after_command(command_name),
                "data": command,
            })
        except Exception as exc:
            await self._emit({
                "type": "assistant_control_error",
                "command": command_name,
                "status": "error",
                "message": f"语音控制命令执行失败：{command_name}，{exc}",
                "data": command,
            })

    def _state_after_command(self, command_name: str) -> str:
        if command_name == "start_listen":
            return "listening"
        if command_name in {"stop_listen", "abort", "abort_speaking"}:
            return "idle"
        return self._snapshot_status()

    async def _start_listening(self, mode: str) -> None:
        from src.constants.constants import ListeningMode

        await self._cmd.connect_protocol()

        if mode == "realtime":
            listen_mode = ListeningMode.REALTIME
        elif mode in {"auto", "auto_stop"}:
            listen_mode = ListeningMode.AUTO_STOP
        else:
            listen_mode = ListeningMode.MANUAL

        await self._cmd.start_listening(listen_mode)

    async def on_device_state_changed(self, state: Any) -> None:
        if not self.enabled:
            return

        state_text = self._state_to_text(state)
        if state_text not in {"idle", "listening", "speaking"}:
            return

        self._last_status = state_text
        await self._emit_state(state_text, self._state_to_message(state_text))

    async def on_incoming_json(self, message: Any) -> None:
        if not self.enabled or not isinstance(message, dict):
            return

        msg_type = message.get("type")

        if msg_type == "stt":
            text = self._clean_text(message.get("text", ""))
            if text:
                await self._emit({
                    "type": "assistant_transcript",
                    "text": text,
                    "message": f"识别文本：{text}",
                    "data": self._safe_json(message),
                })
            return

        if msg_type == "tts":
            state = message.get("state", "")
            text = self._clean_text(message.get("text", ""))

            if state == "start":
                await self._emit_state("speaking", "语音助手正在播报", data=self._safe_json(message))
            elif state == "stop":
                # Do not use snapshot here. During stop, py-xiaozhi can still report
                # a stale speaking/listening snapshot for a short time.
                await self._emit_state("idle", "语音播报结束", data=self._safe_json(message))

            if text:
                await self._emit({
                    "type": "assistant_reply",
                    "text": text,
                    "message": f"助手回复：{text}",
                    "data": self._safe_json(message),
                })
            return

        if msg_type == "llm":
            text = self._clean_text(
                message.get("text")
                or message.get("content")
                or message.get("reply")
                or ""
            )
            if text:
                await self._emit({
                    "type": "assistant_reply",
                    "text": text,
                    "message": f"助手回复：{text}",
                    "data": self._safe_json(message),
                })
            return

        if self.emit_debug_json:
            await self._emit({
                "type": "incoming_json_debug",
                "message": f"收到 JSON：{msg_type or 'unknown'}",
                "data": self._safe_json(message),
            })

    async def on_protocol_connected(self, protocol: Any) -> None:
        if not self.enabled:
            return

        info = {}
        try:
            info = protocol.get_connection_info()
        except Exception:
            info = {"protocol": str(type(protocol))}

        await self._emit({
            "type": "assistant_status",
            "status": "connected",
            "message": "py-xiaozhi 协议已连接",
            "data": self._safe_json(info),
        })

    async def _on_audio_channel_opened(self, _data: Any = None) -> None:
        await self._emit({
            "type": "audio_channel",
            "state": "opened",
            "message": "音频通道已打开",
        })

    async def _on_audio_channel_closed(self, _data: Any = None) -> None:
        await self._emit({
            "type": "audio_channel",
            "state": "closed",
            "message": "音频通道已关闭",
        })

    async def _on_network_error(self, error_message: str | None = None) -> None:
        await self._emit({
            "type": "runtime_error",
            "message": error_message or "py-xiaozhi 网络错误",
            "data": {"error": error_message or ""},
        })

    async def _on_ui_send_text(self, data: Any = None) -> None:
        text = ""

        if hasattr(data, "text"):
            text = str(data.text)
        elif isinstance(data, dict):
            text = str(data.get("text", ""))
        elif isinstance(data, str):
            text = data

        text = self._clean_text(text)
        if text:
            await self._emit({
                "type": "assistant_transcript",
                "text": text,
                "message": f"输入文本：{text}",
                "data": {"input_type": "ui_text"},
            })

    async def _on_ui_listen_start(self, _data: Any = None) -> None:
        await self._emit_state("listening", "用户请求开始监听")

    async def _on_ui_manual_toggle(self, _data: Any = None) -> None:
        await self._emit({
            "type": "assistant_state",
            "state": "manual_toggle",
            "message": "手动录音状态切换",
        })

    async def _on_ui_abort(self, _data: Any = None) -> None:
        await self._emit_state("idle", "用户中断语音输出")

    async def _emit_state(
        self,
        state: str,
        message: str,
        command: dict[str, Any] | None = None,
        data: Any | None = None,
    ) -> None:
        payload = {"state": state}
        if command:
            payload["command"] = command
        if data is not None:
            payload["data"] = data

        await self._emit({
            "type": "assistant_status",
            "status": state,
            "message": message,
            "data": payload,
        })
        await self._emit({
            "type": "assistant_state",
            "state": state,
            "message": message,
            "data": payload,
        })

    async def _emit(self, event: dict[str, Any]) -> None:
        if not self.enabled:
            return

        payload = dict(event)
        payload.setdefault("source", "py-xiaozhi.eventbus_bridge")
        payload.setdefault("created_at", datetime.now(timezone.utc).isoformat())

        try:
            await asyncio.to_thread(self._post_event, payload)
        except Exception:
            logger.debug("PCBridgePlugin: failed to emit event", exc_info=True)

    def _post_event(self, event: dict[str, Any]) -> None:
        data = json.dumps(event, ensure_ascii=False).encode("utf-8")
        request = Request(
            self.event_url,
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
            },
        )

        with urlopen(request, timeout=0.8) as response:
            response.read()

    def _state_to_text(self, state: Any) -> str:
        if hasattr(state, "value"):
            return str(state.value)
        return str(state or "").strip().lower() or "unknown"

    def _state_to_message(self, state: str) -> str:
        mapping = {
            "idle": "语音助手空闲",
            "listening": "语音助手正在聆听",
            "speaking": "语音助手正在播报",
        }
        return mapping.get(state, f"语音助手状态：{state}")

    def _snapshot_status(self) -> str:
        try:
            if self._ctx.is_listening():
                return "listening"
            if self._ctx.is_speaking():
                return "speaking"
            if self._ctx.is_idle():
                return "idle"
        except Exception:
            pass

        return self._last_status or "unknown"

    def _clean_text(self, text: Any) -> str:
        value = "" if text is None else str(text)
        value = value.replace("\r", " ").replace("\n", " ").strip()
        if len(value) > 500:
            value = value[:500] + "..."
        return value

    def _safe_json(self, value: Any) -> Any:
        try:
            json.dumps(value, ensure_ascii=False)
            return value
        except Exception:
            return str(value)
