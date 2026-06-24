from __future__ import annotations

import asyncio
from typing import Any

import httpx

from config import SidecarConfig, load_config
from py_xiaozhi_process_manager import PyXiaozhiProcessManager
from runtime_config_store import get_runtime_config


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
    return PyXiaozhiProcessManager(config).status()


async def collect_status(config: SidecarConfig) -> dict[str, Any]:
    # Runtime path/mode may be edited in .env while Sidecar is running, so reload.
    runtime_config = load_config()
    notes_api = await check_notes_api(runtime_config)
    py_xiaozhi = await asyncio.to_thread(check_py_xiaozhi, runtime_config)

    return {
        "type": "sidecar_status",
        "sidecar": {
            "ok": True,
            "ws_url": config.ws_url,
            "health_url": config.health_url,
        },
        "notes_api": notes_api,
        "py_xiaozhi": py_xiaozhi,
        "runtime_config": get_runtime_config(runtime_config),
    }
