from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from config import SidecarConfig


class PyXiaozhiProcessManager:
    """Best-effort process manager for py-xiaozhi runtime.

    Phase 7.0 goal:
    - Sidecar can detect py-xiaozhi.
    - Sidecar can launch py-xiaozhi.
    - Sidecar can stop/restart py-xiaozhi processes launched from the configured root.
    - The GUI may still appear; start mode is best-effort minimized/hidden.
    """

    def __init__(self, config: SidecarConfig) -> None:
        self.config = config

    def detect_python_exe(self) -> str:
        if self.config.py_xiaozhi_python:
            return self.config.py_xiaozhi_python

        candidates = [
            self.config.py_xiaozhi_root / ".venv" / "Scripts" / "python.exe",
            self.config.py_xiaozhi_root / ".venv" / "Scripts" / "pythonw.exe",
            self.config.py_xiaozhi_root / "venv" / "Scripts" / "python.exe",
            self.config.py_xiaozhi_root / "venv" / "Scripts" / "pythonw.exe",
        ]

        for candidate in candidates:
            if candidate.exists():
                return str(candidate)

        return "python"

    def detect_pythonw_exe(self) -> str:
        python_exe = Path(self.detect_python_exe())

        if python_exe.name.lower() == "pythonw.exe" and python_exe.exists():
            return str(python_exe)

        if python_exe.name.lower() == "python.exe":
            pythonw = python_exe.with_name("pythonw.exe")
            if pythonw.exists():
                return str(pythonw)

        return str(python_exe)

    def main_py(self) -> Path:
        return self.config.py_xiaozhi_root / "main.py"

    def bridge_plugin(self) -> Path:
        return self.config.py_xiaozhi_root / "src" / "plugins" / "pc_bridge.py"

    def notes_tool(self) -> Path:
        return self.config.py_xiaozhi_root / "src" / "mcp" / "tools" / "notes" / "_tools.py"

    def list_processes(self) -> list[dict[str, Any]]:
        if os.name != "nt":
            return []

        root = str(self.config.py_xiaozhi_root).lower().replace("\\", "\\\\")
        processes: list[dict[str, Any]] = []

        # PowerShell is more reliable than tasklist for filtering by command line.
        script = (
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.CommandLine -and $_.CommandLine.ToLower().Contains('"
            + root.replace("'", "''")
            + "') } | "
            "Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress"
        )

        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=5,
            )
        except Exception:
            return []

        raw = result.stdout.strip()
        if not raw:
            return []

        try:
            import json

            payload = json.loads(raw)
            items = payload if isinstance(payload, list) else [payload]
        except Exception:
            return []

        current_pid = os.getpid()

        for item in items:
            try:
                pid = int(item.get("ProcessId"))
            except Exception:
                continue

            if pid == current_pid:
                continue

            command_line = str(item.get("CommandLine") or "")
            name = str(item.get("Name") or "")

            # Avoid matching editor/search tools; require Python or main.py.
            lower_cmd = command_line.lower()
            lower_name = name.lower()
            if "main.py" not in lower_cmd and "python" not in lower_name:
                continue

            processes.append({
                "pid": pid,
                "name": name,
                "command_line": command_line,
            })

        return processes

    def status(self) -> dict[str, Any]:
        processes = self.list_processes()
        python_exe = self.detect_python_exe()
        main_py = self.main_py()

        return {
            "root": str(self.config.py_xiaozhi_root),
            "root_exists": self.config.py_xiaozhi_root.exists(),
            "main_py": str(main_py),
            "main_py_exists": main_py.exists(),
            "python": python_exe,
            "notes_tool_installed": self.notes_tool().exists(),
            "pc_bridge_installed": self.bridge_plugin().exists(),
            "process_running": bool(processes),
            "process_count": len(processes),
            "process_pids": [item["pid"] for item in processes],
            "start_mode": self.config.py_xiaozhi_start_mode,
            "auto_start": self.config.py_xiaozhi_auto_start,
            "launchable": self.config.py_xiaozhi_root.exists() and main_py.exists(),
        }

    def start(self, mode: str | None = None) -> dict[str, Any]:
        current = self.status()
        if current["process_running"]:
            return {
                "ok": True,
                "action": "start",
                "already_running": True,
                "message": "py-xiaozhi 已经在运行",
                "status": current,
            }

        if not current["launchable"]:
            return {
                "ok": False,
                "action": "start",
                "message": "py-xiaozhi 无法启动：root 或 main.py 不存在",
                "status": current,
            }

        start_mode = (mode or self.config.py_xiaozhi_start_mode or "normal").strip().lower()
        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")

        creationflags = 0
        startupinfo = None
        executable = self.detect_python_exe()

        if os.name == "nt":
            creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

            if start_mode in {"hidden", "hide"}:
                creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
                executable = self.detect_pythonw_exe()

            if start_mode in {"minimized", "minimize", "min"}:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 6  # SW_MINIMIZE

        command = [executable, str(self.main_py())]

        try:
            process = subprocess.Popen(
                command,
                cwd=str(self.config.py_xiaozhi_root),
                env=env,
                creationflags=creationflags,
                startupinfo=startupinfo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                close_fds=True,
            )
        except Exception as exc:
            return {
                "ok": False,
                "action": "start",
                "message": f"启动 py-xiaozhi 失败：{exc}",
                "command": command,
                "status": current,
            }

        time.sleep(0.8)
        return {
            "ok": True,
            "action": "start",
            "already_running": False,
            "message": "已请求启动 py-xiaozhi",
            "pid": process.pid,
            "command": command,
            "start_mode": start_mode,
            "status": self.status(),
        }

    def stop(self) -> dict[str, Any]:
        processes = self.list_processes()
        if not processes:
            return {
                "ok": True,
                "action": "stop",
                "already_stopped": True,
                "message": "py-xiaozhi 当前未运行",
                "status": self.status(),
            }

        killed: list[int] = []
        failed: list[dict[str, Any]] = []

        for item in processes:
            pid = int(item["pid"])
            try:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(pid), "/T", "/F"],
                        capture_output=True,
                        text=True,
                        timeout=8,
                    )
                else:
                    os.kill(pid, 15)
                killed.append(pid)
            except Exception as exc:
                failed.append({"pid": pid, "error": str(exc)})

        time.sleep(0.8)
        return {
            "ok": not failed,
            "action": "stop",
            "message": "已请求停止 py-xiaozhi" if not failed else "部分 py-xiaozhi 进程停止失败",
            "killed": killed,
            "failed": failed,
            "status": self.status(),
        }

    def restart(self, mode: str | None = None) -> dict[str, Any]:
        stop_result = self.stop()
        start_result = self.start(mode=mode)
        return {
            "ok": bool(stop_result.get("ok")) and bool(start_result.get("ok")),
            "action": "restart",
            "message": "已请求重启 py-xiaozhi",
            "stop": stop_result,
            "start": start_result,
            "status": self.status(),
        }
