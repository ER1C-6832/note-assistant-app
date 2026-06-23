from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any
from urllib.request import Request, urlopen

from src.logging import get_logger
from src.plugins.base import Plugin

logger = get_logger()


class PCBridgePlugin(Plugin):
    """
    PC Assistant Bridge plugin.

    This is the real Phase 5.4 bridge: it subscribes to py-xiaozhi EventBus and
    plugin callbacks, then forwards runtime events to the local PC Assistant
    Sidecar.

    It is intentionally best-effort:
    - Never blocks user conversation for long.
    - Never raises back into py-xiaozhi runtime.
    - Does not touch notes database directly.
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
        self.emit_debug_json = os.getenv(
            "PC_BRIDGE_DEBUG_JSON",
            "0",
        ).strip().lower() in {"1", "true", "yes", "on"}
        self._registered_handlers: list[tuple[str, Any]] = []
        self._last_status = ""

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

        logger.info("PCBridgePlugin started, forwarding events to %s", self.event_url)

        await self._emit({
            "type": "assistant_status",
            "status": self._snapshot_status(),
            "message": "PC Bridge 已连接 py-xiaozhi EventBus",
        })

    async def stop(self) -> None:
        if not self.enabled:
            return

        try:
            for event_name, handler in self._registered_handlers:
                self._ctx.event_bus.off(event_name, handler)
            self._registered_handlers.clear()
        except Exception:
            pass

        await self._emit({
            "type": "assistant_status",
            "status": "stopped",
            "message": "PC Bridge 已停止",
        })

    async def on_device_state_changed(self, state: Any) -> None:
        if not self.enabled:
            return

        state_text = self._state_to_text(state)
        self._last_status = state_text

        await self._emit({
            "type": "assistant_status",
            "status": state_text,
            "message": f"语音助手状态：{state_text}",
            "data": {"state": state_text},
        })

        await self._emit({
            "type": "assistant_state",
            "state": state_text,
            "message": self._state_to_message(state_text),
            "data": {"state": state_text},
        })

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
                await self._emit({
                    "type": "assistant_state",
                    "state": "speaking",
                    "message": "语音助手正在播报",
                    "data": self._safe_json(message),
                })
            elif state == "stop":
                await self._emit({
                    "type": "assistant_state",
                    "state": self._snapshot_status(),
                    "message": "语音播报结束",
                    "data": self._safe_json(message),
                })

            if text:
                await self._emit({
                    "type": "assistant_reply",
                    "text": text,
                    "message": f"助手回复：{text}",
                    "data": self._safe_json(message),
                })
            return

        if msg_type == "llm":
            # Some servers send emotion only; some may include text.
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
            else:
                emotion = message.get("emotion")
                if emotion:
                    await self._emit({
                        "type": "assistant_state",
                        "state": "emotion",
                        "message": f"助手表情：{emotion}",
                        "data": self._safe_json(message),
                    })
            return

        if msg_type == "mcp":
            await self._emit({
                "type": "assistant_state",
                "state": "tooling",
                "message": "收到 MCP 消息",
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
        await self._emit({
            "type": "assistant_state",
            "state": "listening",
            "message": "用户请求开始监听",
        })

    async def _on_ui_manual_toggle(self, _data: Any = None) -> None:
        await self._emit({
            "type": "assistant_state",
            "state": "manual_toggle",
            "message": "手动录音状态切换",
        })

    async def _on_ui_abort(self, _data: Any = None) -> None:
        await self._emit({
            "type": "assistant_state",
            "state": "aborted",
            "message": "用户中断语音输出",
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
            # Do not break py-xiaozhi if Sidecar is offline.
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
