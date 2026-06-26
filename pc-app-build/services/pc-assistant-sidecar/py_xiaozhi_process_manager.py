from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from config import SidecarConfig, load_config


class PyXiaozhiProcessManager:
    """Process manager for the external py-xiaozhi runtime.

    Phase 8.4:
    - Start returns immediately after Popen.
    - Window hide/minimize is attempted in a short background thread.
    - Process detection timeout is reduced to avoid blocking the Sidecar event loop.
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

        main_py = str(self.main_py()).lower().replace("/", "\\")
        main_literal = main_py.replace("'", "''")
        processes: list[dict[str, Any]] = []

        script = (
            "$main = '" + main_literal + "'; "
            "$slash = [string][char]92; "
            "Get-CimInstance Win32_Process | "
            "Where-Object { "
            "$_.CommandLine -and "
            "($_.Name.ToLower() -eq 'python.exe' -or $_.Name.ToLower() -eq 'pythonw.exe') -and "
            "$_.CommandLine.ToLower().Replace('/', $slash).Contains($main) "
            "} | "
            "Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
        )

        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=1.8,
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
        seen: set[int] = set()

        for item in items:
            try:
                pid = int(item.get("ProcessId"))
            except Exception:
                continue

            if pid == current_pid or pid in seen:
                continue

            command_line = str(item.get("CommandLine") or "")
            name = str(item.get("Name") or "")
            lower_name = name.lower()

            if lower_name not in {"python.exe", "pythonw.exe"}:
                continue

            lower_cmd = command_line.lower().replace("/", "\\")
            if main_py not in lower_cmd:
                continue

            seen.add(pid)
            processes.append({
                "pid": pid,
                "parent_pid": item.get("ParentProcessId"),
                "name": name,
                "command_line": command_line,
            })

        return processes

    def status(self) -> dict[str, Any]:
        processes = self.list_processes()
        return self._status_from_processes(processes)

    def _status_from_processes(self, processes: list[dict[str, Any]]) -> dict[str, Any]:
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

    def _status_from_pid(self, pid: int) -> dict[str, Any]:
        return self._status_from_processes([
            {
                "pid": int(pid),
                "parent_pid": None,
                "name": "pythonw.exe",
                "command_line": str(self.main_py()),
            }
        ])

    def _runtime_args(self) -> list[str]:
        runtime_mode = getattr(self.config, "py_xiaozhi_runtime_mode", "headless") or "headless"
        args = ["--mode", str(runtime_mode), "--protocol", str(self.config.py_xiaozhi_protocol or "websocket")]
        if bool(getattr(self.config, "py_xiaozhi_skip_activation", True)):
            args.append("--skip-activation")
        return args

    def start(self, mode: str | None = None) -> dict[str, Any]:
        self.reload_config()
        existing_processes = self.list_processes()
        current = self._status_from_processes(existing_processes)
        requested_mode = self._normalize_mode(mode or self.config.py_xiaozhi_start_mode)
        requested_window_mode = self._normalize_mode(self.config.py_xiaozhi_window_mode or requested_mode)
        runtime_mode = getattr(self.config, "py_xiaozhi_runtime_mode", "headless") or "headless"

        # Phase 9.3.0.1:
        # GUI runtime must be launched with a visible console/window. A stale
        # hidden/minimized start mode would choose pythonw.exe or hide the window,
        # so selecting GUI looked ineffective.
        if runtime_mode == "gui":
            if requested_mode in {"hidden", "minimized"}:
                requested_mode = "normal"
            requested_window_mode = "normal"

        if current["process_running"]:
            self._apply_window_mode_background(requested_window_mode)
            return {
                "ok": True,
                "action": "start",
                "already_running": True,
                "message": "py-xiaozhi 已经在运行，未重复启动",
                "window_result": {"ok": True, "background": True, "mode": requested_window_mode},
                "status": current,
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

        runtime_mode = getattr(self.config, "py_xiaozhi_runtime_mode", "headless") or "headless"
        env.setdefault("PY_XIAOZHI_MODE", runtime_mode)
        env.setdefault("PY_XIAOZHI_RUNTIME_MODE", runtime_mode)
        if bool(getattr(self.config, "py_xiaozhi_skip_activation", True)):
            env.setdefault("PY_XIAOZHI_SKIP_ACTIVATION", "1")

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

        self._apply_window_mode_background(requested_window_mode)

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
            "window_result": {"ok": True, "background": True, "mode": requested_window_mode},
            "status": self._status_from_pid(process.pid),
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

        sorted_processes = sorted(
            processes,
            key=lambda item: int(item.get("parent_pid") or 0),
            reverse=True,
        )

        for item in sorted_processes:
            pid = int(item["pid"])
            try:
                if os.name == "nt":
                    result = subprocess.run(
                        ["taskkill", "/PID", str(pid), "/T", "/F"],
                        capture_output=True,
                        text=True,
                        timeout=6,
                    )
                    if result.returncode not in {0, 128}:
                        raise RuntimeError((result.stderr or result.stdout or "").strip())
                else:
                    os.kill(pid, 15)
                killed.append(pid)
            except Exception as exc:
                failed.append({"pid": pid, "error": str(exc)})

        time.sleep(0.5)
        remaining = self.list_processes()

        return {
            "ok": not failed and not remaining,
            "action": "stop",
            "message": "已停止 py-xiaozhi" if not failed and not remaining else "py-xiaozhi 停止后仍有残留进程",
            "killed": killed,
            "failed": failed,
            "remaining_pids": [item["pid"] for item in remaining],
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
            "status": start_result.get("status") or self.status(),
        }

    def _apply_window_mode_background(self, mode: str) -> None:
        if self._normalize_mode(mode) == "normal":
            return
        thread = threading.Thread(
            target=lambda: self.apply_window_mode(mode, retries=3, initial_delay=0.4),
            daemon=True,
        )
        thread.start()

    def apply_window_mode(
        self,
        mode: str | None = None,
        retries: int = 3,
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
        last_error = ""

        for _ in range(max(1, retries)):
            processes = self.list_processes()
            if processes:
                result = self._apply_window_mode_to_pids(
                    [item["pid"] for item in processes],
                    normalized,
                )
                changed += int(result.get("changed", 0))
                last_error = str(result.get("error", ""))

                if changed > 0:
                    break

            time.sleep(0.25)

        return {
            "ok": changed > 0 or normalized in {"hidden", "minimized"},
            "action": "apply_window_mode",
            "mode": normalized,
            "message": f"已尝试应用窗口模式：{normalized}",
            "changed": changed,
            "error": last_error,
        }

    def _apply_window_mode_to_pids(self, pids: list[int], mode: str) -> dict[str, Any]:
        if not pids:
            return {"changed": 0}

        show_command = "0" if mode == "hidden" else "6"
        pid_array = ",".join(str(int(pid)) for pid in pids)

        script = f"""
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32ShowWindow {{
  [DllImport("user32.dll")]
  public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
}}
"@;
$changed = 0;
foreach ($pid in @({pid_array})) {{
  try {{
    $p = Get-Process -Id $pid -ErrorAction Stop;
    if ($p.MainWindowHandle -ne 0) {{
      [Win32ShowWindow]::ShowWindowAsync($p.MainWindowHandle, {show_command}) | Out-Null;
      $changed += 1;
    }}
  }} catch {{}}
}}
Write-Output $changed
"""

        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=3,
            )
            changed = int((result.stdout or "0").strip().splitlines()[-1] or "0")
            return {
                "changed": changed,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except Exception as exc:
            return {
                "changed": 0,
                "error": str(exc),
            }

    def _normalize_mode(self, mode: str | None) -> str:
        value = (mode or "").strip().lower()
        if value in {"min", "minimize"}:
            return "minimized"
        if value in {"hide", "no_window", "nowindow", "cli"}:
            return "hidden"
        if value in {"normal", "minimized", "hidden", "debug"}:
            return value
        return "minimized"
