from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any

import httpx

from config import SidecarConfig


def _detect_py_xiaozhi_python(config: SidecarConfig) -> str:
    if config.py_xiaozhi_python:
        return config.py_xiaozhi_python

    candidates = [
        config.py_xiaozhi_root / ".venv" / "Scripts" / "python.exe",
        config.py_xiaozhi_root / "venv" / "Scripts" / "python.exe",
    ]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    return "python"


def _is_process_running(process_name_or_path: str) -> bool:
    if os.name != "nt":
        return False

    try:
        result = subprocess.run(
            ["tasklist"],
            capture_output=True,
            text=True,
            encoding="mbcs",
            errors="ignore",
            timeout=4,
        )
    except Exception:
        return False

    haystack = result.stdout.lower()
    needle = process_name_or_path.lower()

    if needle.endswith(".py"):
        return "python.exe" in haystack or "pythonw.exe" in haystack

    return needle in haystack


async def check_notes_api(config: SidecarConfig) -> dict[str, Any]:
    url = f"{config.notes_api_base_url}/api/health"

    try:
        async with httpx.AsyncClient(timeout=2.0, trust_env=False) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
        return {
            "ok": True,
            "url": url,
            "detail": payload,
        }
    except Exception as exc:
        return {
            "ok": False,
            "url": url,
            "error": str(exc),
        }


def check_py_xiaozhi(config: SidecarConfig) -> dict[str, Any]:
    root = config.py_xiaozhi_root
    main_py = root / "main.py"
    notes_tool = root / "src" / "mcp" / "tools" / "notes" / "_tools.py"
    python_exe = _detect_py_xiaozhi_python(config)

    return {
        "root": str(root),
        "root_exists": root.exists(),
        "main_py_exists": main_py.exists(),
        "notes_tool_installed": notes_tool.exists(),
        "python": python_exe,
        "process_running": _is_process_running("python.exe"),
    }


async def collect_status(config: SidecarConfig) -> dict[str, Any]:
    notes_api = await check_notes_api(config)
    py_xiaozhi = await asyncio.to_thread(check_py_xiaozhi, config)

    return {
        "type": "sidecar_status",
        "sidecar": {
            "ok": True,
            "ws_url": config.ws_url,
            "health_url": config.health_url,
        },
        "notes_api": notes_api,
        "py_xiaozhi": py_xiaozhi,
    }
