from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import websockets
from websockets.server import WebSocketServerProtocol

from config import SidecarConfig
from notes_watcher import NotesSnapshotWatcher
from status_checker import collect_status

logger = logging.getLogger("sidecar.ws")


class SidecarWebSocketServer:
    def __init__(self, config: SidecarConfig) -> None:
        self.config = config
        self.clients: set[WebSocketServerProtocol] = set()
        self.watcher = NotesSnapshotWatcher(config)
        self._stop = asyncio.Event()

    async def start(self) -> None:
        logger.info("Starting WebSocket server on %s", self.config.ws_url)

        async with websockets.serve(
            self._handle_client,
            self.config.ws_host,
            self.config.ws_port,
            ping_interval=20,
            ping_timeout=20,
        ):
            tasks = [
                asyncio.create_task(self._status_loop()),
                asyncio.create_task(self._notes_watch_loop()),
            ]

            try:
                await self._stop.wait()
            finally:
                for task in tasks:
                    task.cancel()

    async def _handle_client(self, websocket: WebSocketServerProtocol) -> None:
        # websockets versions expose path differently. In 5.1.1 we accept the
        # connection and rely on the fixed endpoint configured by the app.
        self.clients.add(websocket)
        logger.info("Client connected: %s", getattr(websocket, "remote_address", ""))

        await self._send(websocket, {
            "type": "sidecar_connected",
            "message": "PC Assistant Sidecar connected",
            "ws_url": self.config.ws_url,
        })
        await self._send(websocket, await collect_status(self.config))

        try:
            async for raw_message in websocket:
                await self._handle_message(websocket, raw_message)
        except websockets.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)
            logger.info("Client disconnected: %s", getattr(websocket, "remote_address", ""))

    async def _handle_message(
        self,
        websocket: WebSocketServerProtocol,
        raw_message: str,
    ) -> None:
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            await self._send(websocket, {
                "type": "error",
                "message": "Invalid JSON message",
            })
            return

        message_type = message.get("type")

        if message_type == "ping":
            await self._send(websocket, {"type": "pong"})
            return

        if message_type == "refresh_status":
            await self._send(websocket, await collect_status(self.config))
            return

        if message_type == "refresh_notes":
            await self.broadcast({
                "type": "notes_changed",
                "reason": "manual_refresh",
            })
            return

        await self._send(websocket, {
            "type": "error",
            "message": f"Unknown message type: {message_type}",
        })

    async def _status_loop(self) -> None:
        while True:
            await asyncio.sleep(5)
            await self.broadcast(await collect_status(self.config))

    async def _notes_watch_loop(self) -> None:
        while True:
            try:
                changed = await self.watcher.check_changed()

                if changed:
                    logger.info("Broadcast notes_changed: %s", changed.get("reason"))
                    await self.broadcast(changed)
            except Exception as exc:
                logger.debug("Notes watch failed: %s", exc)

            await asyncio.sleep(self.config.poll_interval_seconds)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        if not self.clients:
            return

        raw = json.dumps(payload, ensure_ascii=False)
        closed = []

        for client in list(self.clients):
            try:
                await client.send(raw)
            except websockets.ConnectionClosed:
                closed.append(client)

        for client in closed:
            self.clients.discard(client)

    async def _send(
        self,
        websocket: WebSocketServerProtocol,
        payload: dict[str, Any],
    ) -> None:
        await websocket.send(json.dumps(payload, ensure_ascii=False))
