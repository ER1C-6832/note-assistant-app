from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from urllib.request import urlopen

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from app_ws_server import SidecarWebSocketServer
from config import SidecarConfig, load_config
from control_store import ControlCommandHub
from event_store import SidecarEventHub
from health_server import start_health_server
from py_xiaozhi_log_watcher import PyXiaozhiLogWatcher
from py_xiaozhi_process_manager import PyXiaozhiProcessManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("websockets.server").setLevel(logging.WARNING)

logger = logging.getLogger("sidecar")


def _existing_sidecar_is_healthy(config: SidecarConfig) -> bool:
    try:
        with urlopen(config.health_url, timeout=1.0) as response:
            if response.status != 200:
                return False
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
            return bool(payload.get("ok"))
    except Exception:
        return False


async def main() -> None:
    config = load_config()

    if _existing_sidecar_is_healthy(config):
        logger.info("PC Assistant Sidecar is already running: %s", config.health_url)
        logger.info("Skip starting a duplicate Sidecar process.")
        return

    logger.info("PC Assistant Sidecar starting...")
    logger.info("PC build root: %s", config.pc_build_root)
    logger.info("Notes API: %s", config.notes_api_base_url)
    logger.info("py-xiaozhi root: %s", config.py_xiaozhi_root)
    logger.info("py-xiaozhi log: %s", getattr(config, "py_xiaozhi_log_path", ""))
    logger.info("py-xiaozhi start mode: %s", config.py_xiaozhi_start_mode)
    logger.info("py-xiaozhi auto start: %s", config.py_xiaozhi_auto_start)
    logger.info("WebSocket: %s", config.ws_url)
    logger.info("Health: %s", config.health_url)

    event_hub = SidecarEventHub()
    control_hub = ControlCommandHub()
    runtime_manager = PyXiaozhiProcessManager(config)

    if config.py_xiaozhi_auto_start:
        start_result = await asyncio.to_thread(runtime_manager.start)
        logger.info("py-xiaozhi auto start: %s", start_result.get("message"))

    ws_server = SidecarWebSocketServer(
        config,
        event_hub=event_hub,
        control_hub=control_hub,
        runtime_manager=runtime_manager,
    )
    log_watcher = PyXiaozhiLogWatcher(config, event_hub)

    try:
        await asyncio.gather(
            ws_server.start(),
            start_health_server(
                config,
                event_hub=event_hub,
                control_hub=control_hub,
                runtime_manager=runtime_manager,
            ),
            log_watcher.run(),
        )
    except OSError as exc:
        if getattr(exc, "winerror", None) == 10048 or getattr(exc, "errno", None) == 10048:
            logger.warning("Sidecar port is already in use. Another Sidecar is probably running.")
            logger.warning("Check: %s", config.health_url)
            return
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("PC Assistant Sidecar stopped.")
