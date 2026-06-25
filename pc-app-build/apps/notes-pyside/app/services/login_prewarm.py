from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Type

from PySide6.QtCore import Property, Slot

TASK_NAME = "NoteAssistantVoicePrewarm"
ENV_KEY = "PC_APP_LOGIN_PREWARM_ENABLED"


def _pc_build_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _env_path() -> Path:
    return _pc_build_root() / ".env"


def _read_env_lines() -> list[str]:
    path = _env_path()
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def _read_env_bool(key: str, default: bool = False) -> bool:
    prefix = key.lower()
    for line in _read_env_lines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        if name.strip().lower() == prefix:
            return value.strip().lower() in {"1", "true", "yes", "y", "on", "是"}
    return default


def _write_env_value(key: str, value: str) -> None:
    lines = _read_env_lines()
    out: list[str] = []
    found = False
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            name, _ = stripped.split("=", 1)
            if name.strip().lower() == key.lower():
                out.append(f"{key}={value}")
                found = True
                continue
        out.append(line)
    if not found:
        if out and out[-1].strip():
            out.append("")
        out.append(f"{key}={value}")
    _env_path().write_text("\n".join(out) + "\n", encoding="utf-8")
    os.environ[key] = value


def _run_command(args: list[str], timeout: float = 8.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=str(_pc_build_root()),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        shell=False,
    )


def _run_script(script_name: str) -> subprocess.CompletedProcess:
    script = _pc_build_root() / "scripts" / script_name
    return subprocess.run(
        [str(script)],
        cwd=str(_pc_build_root()),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=12,
        shell=True,
    )


def _task_installed() -> bool:
    try:
        result = _run_command(["schtasks", "/Query", "/TN", TASK_NAME], timeout=5)
        return result.returncode == 0
    except Exception:
        return False


def apply_login_prewarm_patch(sidecar_client_cls: Type) -> None:
    if getattr(sidecar_client_cls, "_login_prewarm_patch_applied", False):
        return

    def refresh_login_prewarm_status(self) -> None:
        env_enabled = _read_env_bool(ENV_KEY, False)
        task_exists = _task_installed()
        self._login_prewarm_enabled = bool(env_enabled and task_exists)
        if env_enabled and task_exists:
            self._login_prewarm_status_text = "Windows 登录预热已启用"
        elif env_enabled and not task_exists:
            self._login_prewarm_status_text = "已在 .env 启用，但计划任务未安装"
        elif task_exists:
            self._login_prewarm_status_text = "计划任务存在，但 .env 未启用"
        else:
            self._login_prewarm_status_text = "Windows 登录预热未启用"
        self.statusChanged.emit()

    def get_login_prewarm_enabled(self) -> bool:
        if not hasattr(self, "_login_prewarm_enabled"):
            refresh_login_prewarm_status(self)
        return bool(getattr(self, "_login_prewarm_enabled", False))

    def get_login_prewarm_status_text(self) -> str:
        if not hasattr(self, "_login_prewarm_status_text"):
            refresh_login_prewarm_status(self)
        return str(getattr(self, "_login_prewarm_status_text", "Windows 登录预热未确认"))

    def set_login_prewarm_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        try:
            _write_env_value(ENV_KEY, "1" if enabled else "0")
            if enabled:
                result = _run_script("install_login_prewarm_task.bat")
            else:
                result = _run_script("uninstall_login_prewarm_task.bat")
            output = (result.stdout or "").strip().replace("\r", " ").replace("\n", " ")
            self._last_runtime_config_text = output[-240:] if output else (
                "Windows 登录预热已启用" if enabled else "Windows 登录预热已关闭"
            )
        except Exception as exc:
            self._last_runtime_config_text = f"Windows 登录预热设置失败：{str(exc)[:160]}"
        refresh_login_prewarm_status(self)

    sidecar_client_cls.loginPrewarmEnabled = Property(  # type: ignore[attr-defined]
        bool,
        get_login_prewarm_enabled,
        notify=sidecar_client_cls.statusChanged,
    )
    sidecar_client_cls.loginPrewarmStatusText = Property(  # type: ignore[attr-defined]
        str,
        get_login_prewarm_status_text,
        notify=sidecar_client_cls.statusChanged,
    )
    sidecar_client_cls.refreshLoginPrewarmStatus = Slot()(refresh_login_prewarm_status)  # type: ignore[attr-defined]
    sidecar_client_cls.setLoginPrewarmEnabled = Slot(bool)(set_login_prewarm_enabled)  # type: ignore[attr-defined]
    sidecar_client_cls._login_prewarm_patch_applied = True
