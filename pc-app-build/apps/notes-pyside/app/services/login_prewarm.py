from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot

TASK_NAME = "NoteAssistantVoicePrewarm"
ENV_KEY = "PC_APP_LOGIN_PREWARM_ENABLED"


class LoginPrewarmController(QObject):
    statusChanged = Signal()

    def __init__(self, pc_build_root: Path) -> None:
        super().__init__()
        self._pc_build_root = Path(pc_build_root)
        self._login_prewarm_enabled = False
        self._login_prewarm_status_text = "Windows 登录预热未确认"
        self.refreshLoginPrewarmStatus()

    def _env_path(self) -> Path:
        return self._pc_build_root / ".env"

    def _read_env_lines(self) -> list[str]:
        path = self._env_path()
        if not path.exists():
            return []
        return path.read_text(encoding="utf-8").splitlines()

    def _read_env_bool(self, key: str, default: bool = False) -> bool:
        for raw_line in self._read_env_lines():
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name, value = stripped.split("=", 1)
            if name.strip().lower() == key.lower():
                return value.strip().strip('"').strip("'").lower() in {"1", "true", "yes", "y", "on", "是"}
        return default

    def _write_env_value(self, key: str, value: str) -> None:
        lines = self._read_env_lines()
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

        self._env_path().write_text("\n".join(out) + "\n", encoding="utf-8")
        os.environ[key] = value

    def _run_command(self, args: list[str], timeout: float = 8.0) -> subprocess.CompletedProcess:
        return subprocess.run(
            args,
            cwd=str(self._pc_build_root),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            shell=False,
        )

    def _run_script(self, script_name: str) -> subprocess.CompletedProcess:
        script = self._pc_build_root / "scripts" / script_name
        return subprocess.run(
            [str(script)],
            cwd=str(self._pc_build_root),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=12,
            shell=True,
        )

    def _task_installed(self) -> bool:
        try:
            result = self._run_command(["schtasks", "/Query", "/TN", TASK_NAME], timeout=5)
            return result.returncode == 0
        except Exception:
            return False

    @Property(bool, notify=statusChanged)
    def loginPrewarmEnabled(self) -> bool:
        return bool(self._login_prewarm_enabled)

    @Property(str, notify=statusChanged)
    def loginPrewarmStatusText(self) -> str:
        return self._login_prewarm_status_text

    @Slot()
    def refreshLoginPrewarmStatus(self) -> None:
        env_enabled = self._read_env_bool(ENV_KEY, False)
        task_exists = self._task_installed()

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

    @Slot(bool)
    def setLoginPrewarmEnabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        try:
            self._write_env_value(ENV_KEY, "1" if enabled else "0")
            if enabled:
                result = self._run_script("install_login_prewarm_task.bat")
            else:
                result = self._run_script("uninstall_login_prewarm_task.bat")

            output = (result.stdout or "").strip().replace("\r", " ").replace("\n", " ")
            if result.returncode != 0:
                self._login_prewarm_status_text = f"Windows 登录预热设置失败：{output[-180:]}"
            else:
                self._login_prewarm_status_text = output[-180:] if output else (
                    "Windows 登录预热已启用" if enabled else "Windows 登录预热已关闭"
                )
        except Exception as exc:
            self._login_prewarm_status_text = f"Windows 登录预热设置失败：{str(exc)[:160]}"

        self.refreshLoginPrewarmStatus()
