from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any

from config import SidecarConfig, load_config


class PyXiaozhiProcessManager:
    """Best-effort process manager for py-xiaozhi runtime.

    Phase 7.0.1:
    - Adds real best-effort window hide/minimize after launch.
    - Supports existing PY_XIAOZHI_MODE=cli as hidden mode alias.
    - Starting an already-running py-xiaozhi reapplies window mode.
    """

    def __init__(self, config: SidecarConfig) -> None:
        self.config = config

    def reload_config(self) -> SidecarConfig:
        self.config = load_config()
        return self.config

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
            "runtime_mode": self.config.py_xiaozhi_runtime_mode,
            "protocol": self.config.py_xiaozhi_protocol,
            "skip_activation": self.config.py_xiaozhi_skip_activation,
            "start_mode": self.config.py_xiaozhi_start_mode,
            "window_mode": self.config.py_xiaozhi_window_mode,
            "auto_start": self.config.py_xiaozhi_auto_start,
            "launchable": self.config.py_xiaozhi_root.exists() and main_py.exists(),
        }

    def _runtime_args(self) -> list[str]:
        runtime_mode = getattr(self.config, "py_xiaozhi_runtime_mode", "headless") or "headless"
        args = ["--mode", str(runtime_mode), "--protocol", str(self.config.py_xiaozhi_protocol or "websocket")]
        if bool(getattr(self.config, "py_xiaozhi_skip_activation", False)):
            args.append("--skip-activation")
        return args

    def start(self, mode: str | None = None) -> dict[str, Any]:
        current = self.status()
        self.reload_config()
        requested_mode = self._normalize_mode(mode or self.config.py_xiaozhi_start_mode)
        requested_window_mode = self._normalize_mode(self.config.py_xiaozhi_window_mode or requested_mode)

        if current["process_running"]:
            window_result = self.apply_window_mode(requested_window_mode)
            return {
                "ok": True,
                "action": "start",
                "already_running": True,
                "message": "py-xiaozhi 已经在运行，已重新应用窗口模式",
                "window_result": window_result,
                "status": self.status(),
            }

        if not current["launchable"]:
            return {
                "ok": False,
                "action": "start",
                "message": "py-xiaozhi 无法启动：root 或 main.py 不存在",
                "status": current,
            }

        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")

        # Preserve existing PY_XIAOZHI_MODE=cli for py-xiaozhi itself if the repo uses it.
        runtime_mode = getattr(self.config, "py_xiaozhi_runtime_mode", "headless") or "headless"
        env.setdefault("PY_XIAOZHI_MODE", runtime_mode)
        env.setdefault("PY_XIAOZHI_RUNTIME_MODE", runtime_mode)

        if requested_mode == "hidden":
            env.setdefault("PY_XIAOZHI_WINDOW_MODE", "hidden")

        creationflags = 0
        startupinfo = None
        executable = self.detect_python_exe()

        if os.name == "nt":
            creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

            if requested_mode == "hidden":
                creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
                executable = self.detect_pythonw_exe()

            if runtime_mode == "headless" and requested_mode != "debug":
                executable = self.detect_pythonw_exe()

            if requested_mode == "minimized":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 6  # SW_MINIMIZE

        command = [executable, str(self.main_py()), *self._runtime_args()]

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

        window_result = self.apply_window_mode(requested_window_mode, retries=18, initial_delay=0.5)

        return {
            "ok": True,
            "action": "start",
            "already_running": False,
            "message": "已请求启动 py-xiaozhi",
            "pid": process.pid,
            "command": command,
            "runtime_mode": runtime_mode,
            "start_mode": requested_mode,
            "window_mode": requested_window_mode,
            "window_result": window_result,
            "status": self.status(),
        }

    def stop(self) -> dict[str, Any]:
        self.reload_config()
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

    def apply_window_mode(
        self,
        mode: str | None = None,
        retries: int = 10,
        initial_delay: float = 0.0,
    ) -> dict[str, Any]:
        normalized = self._normalize_mode(mode or self.config.py_xiaozhi_window_mode)
        if normalized == "normal":
            return {
                "ok": True,
                "action": "apply_window_mode",
                "mode": normalized,
                "message": "窗口模式为 normal，无需处理",
                "changed": 0,
            }

        if os.name != "nt":
            return {
                "ok": False,
                "action": "apply_window_mode",
                "mode": normalized,
                "message": "当前系统不是 Windows，无法隐藏/最小化窗口",
                "changed": 0,
            }

        if initial_delay > 0:
            time.sleep(initial_delay)

        changed = 0
        attempts = 0
        pids_seen: list[int] = []

        for _ in range(max(1, retries)):
            attempts += 1
            processes = self.list_processes()
            pids = [int(item["pid"]) for item in processes]
            pids_seen = pids

            if pids:
                changed = self._apply_window_mode_to_pids(pids, normalized)
                if changed > 0:
                    break

            time.sleep(0.25)

        return {
            "ok": changed > 0 or bool(pids_seen),
            "action": "apply_window_mode",
            "mode": normalized,
            "message": (
                f"已尝试{self._mode_text(normalized)} py-xiaozhi 窗口"
                if pids_seen else
                "未找到 py-xiaozhi 进程，无法应用窗口模式"
            ),
            "changed": changed,
            "attempts": attempts,
            "pids": pids_seen,
        }

    def _apply_window_mode_to_pids(self, pids: list[int], mode: str) -> int:
        if not pids:
            return 0

        # SW_HIDE = 0, SW_MINIMIZE = 6
        show_command = 0 if mode == "hidden" else 6

        pid_list = ",".join(str(pid) for pid in pids)
        ps_script = f"""
$code = @"
using System;
using System.Runtime.InteropServices;
public class Win32 {{
    [DllImport("user32.dll")]
    public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
}}
"@
try {{
    Add-Type $code -ErrorAction SilentlyContinue | Out-Null
}} catch {{}}
$changed = 0
$pids = @({pid_list})
foreach ($pid in $pids) {{
    $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
    if ($proc -and $proc.MainWindowHandle -ne 0) {{
        [Win32]::ShowWindowAsync($proc.MainWindowHandle, {show_command}) | Out-Null
        $changed += 1
    }}
}}
Write-Output $changed
"""

        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=5,
            )
            raw = (result.stdout or "").strip().splitlines()
            return int(raw[-1]) if raw else 0
        except Exception:
            return 0

    def _normalize_mode(self, value: str | None) -> str:
        mode = (value or "").strip().lower()
        aliases = {
            "min": "minimized",
            "minimize": "minimized",
            "minimized": "minimized",
            "hide": "hidden",
            "hidden": "hidden",
            "no_window": "hidden",
            "nowindow": "hidden",
            "normal": "normal",
            "gui": "normal",
            "cli": "hidden",
        }
        if mode == "debug":
            return "normal"
        return aliases.get(mode, "minimized")

    def _mode_text(self, mode: str) -> str:
        return "隐藏" if mode == "hidden" else "最小化" if mode == "minimized" else "恢复"
