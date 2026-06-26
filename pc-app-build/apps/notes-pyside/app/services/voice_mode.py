from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot


_TRUE_VALUES = {"1", "true", "yes", "y", "on", "是"}
_FALSE_VALUES = {"0", "false", "no", "n", "off", "否"}


def _as_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in _TRUE_VALUES:
        return True
    if text in _FALSE_VALUES:
        return False
    return default


class VoiceModeController(QObject):
    """Small settings controller for voice interaction mode."""

    statusChanged = Signal()

    def __init__(self, pc_build_root: Path) -> None:
        super().__init__()
        self._pc_build_root = Path(pc_build_root)
        self._env_path = self._pc_build_root / ".env"
        self._continuous_enabled = self._read_env_bool(
            "PC_APP_CONTINUOUS_CONVERSATION_ENABLED",
            default=False,
        )
        self._just_changed = False
        self._status_text = self._status_message()

    @Property(bool, notify=statusChanged)
    def continuousConversationEnabled(self) -> bool:
        return bool(self._continuous_enabled)

    @Property(str, notify=statusChanged)
    def continuousConversationStatusText(self) -> str:
        return self._status_text

    @Slot()
    def refreshVoiceModeStatus(self) -> None:
        self._continuous_enabled = self._read_env_bool(
            "PC_APP_CONTINUOUS_CONVERSATION_ENABLED",
            default=False,
        )
        self._just_changed = False
        self._status_text = self._status_message()
        self.statusChanged.emit()

    @Slot(bool)
    def setContinuousConversationEnabled(self, enabled: bool) -> None:
        self._continuous_enabled = bool(enabled)
        self._just_changed = True
        os.environ["PC_APP_CONTINUOUS_CONVERSATION_ENABLED"] = "1" if enabled else "0"
        self._update_env_file({
            "PC_APP_CONTINUOUS_CONVERSATION_ENABLED": "1" if enabled else "0",
        })
        self._status_text = self._status_message()
        self.statusChanged.emit()

    def _status_message(self) -> str:
        restart_hint = " 建议重启语音助手或重启应用后再测试，连续对话状态会更稳定。" if self._just_changed else ""
        if self._continuous_enabled:
            return "连续对话已开启：点击说话会进入自动连续聆听；点击停止后退出。" + restart_hint
        return "连续对话已关闭：点击说话只进行单轮语音操作。" + restart_hint

    def _read_env_bool(self, key: str, default: bool = False) -> bool:
        file_value = self._read_env_file_value(key)
        if file_value is not None:
            return _as_bool(file_value, default=default)
        return _as_bool(os.getenv(key), default=default)

    def _read_env_file_value(self, key: str) -> str | None:
        if not self._env_path.exists():
            return None
        try:
            for raw_line in self._env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, value = line.split("=", 1)
                if name.strip() == key:
                    return value.strip().strip('"').strip("'")
        except Exception:
            return None
        return None

    def _update_env_file(self, updates: dict[str, str]) -> None:
        self._env_path.parent.mkdir(parents=True, exist_ok=True)

        lines = self._env_path.read_text(encoding="utf-8").splitlines() if self._env_path.exists() else []
        output: list[str] = []
        seen: set[str] = set()

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in line:
                output.append(line)
                continue

            key, _value = line.split("=", 1)
            key = key.strip()
            if key in updates:
                output.append(f"{key}={updates[key]}")
                seen.add(key)
            else:
                output.append(line)

        missing = [key for key in updates if key not in seen]
        if missing:
            if output and output[-1].strip():
                output.append("")
            output.append("# PC App voice interaction mode")
            for key in missing:
                output.append(f"{key}={updates[key]}")

        self._env_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
