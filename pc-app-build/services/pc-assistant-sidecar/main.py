"""
PC Assistant Sidecar — entry point.

Starts the WebSocket server, initializes the py-xiaozhi runtime,
and listens for client connections from the PySide6 desktop app.
"""

import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sidecar")


async def main():
    logger.info("PC Assistant Sidecar starting...")
    # Placeholder — Phase 5 will implement the WebSocket server
    # and py-xiaozhi lifecycle management.
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
