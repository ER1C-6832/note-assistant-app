"""Deterministic Xiaozhi JSON message builder shared by Fake and Real transports."""

from __future__ import annotations

import json


def _compact(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class XiaozhiMessageBuilder:
    """Build protocol messages without hand-written JSON escaping."""

    def hello(self) -> str:
        return _compact(
            {
                "type": "hello",
                "version": 1,
                "features": {"mcp": True},
                "transport": "websocket",
                "audio_params": {
                    "format": "opus",
                    "sample_rate": 16_000,
                    "channels": 1,
                    "frame_duration": 20,
                },
            }
        )

    def listen_detect(self, session_id: str, text: str) -> str:
        return _compact(
            {
                "session_id": session_id,
                "type": "listen",
                "state": "detect",
                "text": text,
            }
        )

    def start_listening(self, session_id: str, mode: str = "manual") -> str:
        return _compact(
            {
                "session_id": session_id,
                "type": "listen",
                "state": "start",
                "mode": mode,
            }
        )

    def stop_listening(self, session_id: str) -> str:
        return _compact(
            {
                "session_id": session_id,
                "type": "listen",
                "state": "stop",
            }
        )

    def abort(self, session_id: str, reason: str = "user_interruption") -> str:
        return _compact(
            {
                "session_id": session_id,
                "type": "abort",
                "reason": reason,
            }
        )

    def mcp(self, session_id: str, payload: dict[str, object]) -> str:
        return _compact(
            {
                "session_id": session_id,
                "type": "mcp",
                "payload": payload,
            }
        )
