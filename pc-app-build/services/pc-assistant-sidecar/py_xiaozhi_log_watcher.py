from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Any

from config import SidecarConfig
from event_store import SidecarEventHub

logger = logging.getLogger("sidecar.py_xiaozhi_log")


class PyXiaozhiLogWatcher:
    """
    Lightweight py-xiaozhi runtime log bridge.

    It does not modify py-xiaozhi internals. It tails the runtime log and emits:
    - assistant_log
    - assistant_transcript
    - assistant_reply
    - assistant_state

    The matcher is deliberately conservative. Unknown log lines are ignored
    unless they contain likely user / assistant / state markers.
    """

    def __init__(self, config: SidecarConfig, event_hub: SidecarEventHub) -> None:
        self.config = config
        self.event_hub = event_hub
        self.log_path = config.py_xiaozhi_log_path
        self._position = 0
        self._last_size = 0

    async def run(self) -> None:
        if self.log_path is None:
            logger.warning("py-xiaozhi log path is not configured.")
            return

        logger.info("Watching py-xiaozhi log: %s", self.log_path)

        while True:
            try:
                await self._poll_once()
            except Exception as exc:
                logger.debug("py-xiaozhi log watcher failed: %s", exc)

            await asyncio.sleep(self.config.log_poll_interval_seconds)

    async def _poll_once(self) -> None:
        path = Path(self.log_path)

        if not path.exists():
            return

        size = path.stat().st_size

        # First poll starts at EOF to avoid replaying a huge historical log.
        if self._position == 0 and self._last_size == 0:
            self._position = size
            self._last_size = size
            await self.event_hub.publish({
                "type": "assistant_state",
                "source": "py-xiaozhi.log_watcher",
                "state": "log_watching",
                "message": f"开始监听 py-xiaozhi 日志：{path}",
            })
            return

        # Log rotation / truncation.
        if size < self._position:
            self._position = 0

        with path.open("r", encoding="utf-8", errors="replace") as file:
            file.seek(self._position)
            chunk = file.read()
            self._position = file.tell()

        self._last_size = size

        if not chunk:
            return

        for line in chunk.splitlines():
            event = self._parse_line(line)
            if event:
                await self.event_hub.publish(event)

    def _parse_line(self, line: str) -> dict[str, Any] | None:
        clean = line.strip()
        if not clean:
            return None

        # Remove timestamp/logger prefix when present, but keep original line.
        message = clean
        bracket_idx = message.find("] ")
        if bracket_idx >= 0:
            message = message[bracket_idx + 2:].strip()

        # Common Chinese / English transcript markers.
        transcript = self._extract_after_markers(
            message,
            [
                "识别结果:",
                "识别结果：",
                "用户说:",
                "用户说：",
                "用户:",
                "用户：",
                "User:",
                "ASR:",
                "STT:",
            ],
        )
        if transcript:
            return {
                "type": "assistant_transcript",
                "source": "py-xiaozhi.log_watcher",
                "text": transcript,
                "message": f"识别文本：{transcript}",
                "raw": clean,
            }

        reply = self._extract_after_markers(
            message,
            [
                "助手回复:",
                "助手回复：",
                "回复:",
                "回复：",
                "小智:",
                "小智：",
                "Assistant:",
                "LLM:",
                "TTS:",
            ],
        )
        if reply:
            return {
                "type": "assistant_reply",
                "source": "py-xiaozhi.log_watcher",
                "text": reply,
                "message": f"助手回复：{reply}",
                "raw": clean,
            }

        lowered = message.lower()

        if any(key in lowered for key in ["listening", "wake", "wakeup", "listened"]):
            return {
                "type": "assistant_state",
                "source": "py-xiaozhi.log_watcher",
                "state": "listening",
                "message": "语音助手正在监听",
                "raw": clean,
            }

        if any(key in message for key in ["聆听", "唤醒", "开始录音", "正在听"]):
            return {
                "type": "assistant_state",
                "source": "py-xiaozhi.log_watcher",
                "state": "listening",
                "message": "语音助手正在监听",
                "raw": clean,
            }

        if any(key in message for key in ["开始播放", "播放音频", "TTS", "语音合成"]):
            return {
                "type": "assistant_state",
                "source": "py-xiaozhi.log_watcher",
                "state": "speaking",
                "message": "语音助手正在播报",
                "raw": clean,
            }

        # Do not flood UI with every debug line.
        return None

    def _extract_after_markers(self, message: str, markers: list[str]) -> str:
        for marker in markers:
            if marker in message:
                value = message.split(marker, 1)[1].strip()
                return self._clean_value(value)
        return ""

    def _clean_value(self, value: str) -> str:
        value = value.strip().strip('"').strip("'")
        value = re.sub(r"\s+", " ", value).strip()
        if len(value) > 220:
            value = value[:220] + "..."
        return value
