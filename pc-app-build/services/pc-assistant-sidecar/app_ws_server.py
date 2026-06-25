from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import websockets
from websockets.server import WebSocketServerProtocol

from config import SidecarConfig, load_config
from control_store import ControlCommandHub
from event_store import SidecarEventHub
from notes_watcher import NotesSnapshotWatcher
from py_xiaozhi_process_manager import PyXiaozhiProcessManager
from runtime_config_store import get_runtime_config, save_runtime_config
from status_checker import collect_status

logger = logging.getLogger("sidecar.ws")


class SidecarWebSocketServer:
    def __init__(
        self,
        config: SidecarConfig,
        event_hub: SidecarEventHub | None = None,
        control_hub: ControlCommandHub | None = None,
        runtime_manager: PyXiaozhiProcessManager | None = None,
    ) -> None:
        self.config = config
        self.clients: set[WebSocketServerProtocol] = set()
        self.watcher = NotesSnapshotWatcher(config)
        self.event_hub = event_hub or SidecarEventHub()
        self.control_hub = control_hub or ControlCommandHub()
        self.runtime_manager = runtime_manager or PyXiaozhiProcessManager(config)
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
                asyncio.create_task(self._event_loop()),
            ]

            try:
                await self._stop.wait()
            finally:
                for task in tasks:
                    task.cancel()

    async def _handle_client(self, websocket: WebSocketServerProtocol) -> None:
        self.clients.add(websocket)
        logger.info("Client connected: %s", getattr(websocket, "remote_address", ""))

        await self._send(websocket, {
            "type": "sidecar_connected",
            "message": "PC Assistant Sidecar connected",
            "ws_url": self.config.ws_url,
        })
        await self._send(websocket, get_runtime_config(load_config()))
        await self._send(websocket, await collect_status(self.config))
        await self._send(websocket, {
            "type": "sidecar_events",
            "items": self.event_hub.recent_events(limit=20),
        })

        try:
            async for raw_message in websocket:
                await self._handle_message(websocket, raw_message)
        except websockets.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)
            logger.info("Client disconnected: %s", getattr(websocket, "remote_address", ""))

    async def _handle_message(self, websocket: WebSocketServerProtocol, raw_message: str) -> None:
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            await self._send(websocket, {"type": "error", "message": "Invalid JSON message"})
            return

        message_type = message.get("type")

        if message_type == "ping":
            await self._send(websocket, {"type": "pong"})
            return

        if message_type == "refresh_status":
            await self._send(websocket, await collect_status(self.config))
            return

        if message_type == "get_runtime_config":
            await self._send(websocket, get_runtime_config(load_config()))
            return

        if message_type == "save_runtime_config":
            result = await asyncio.to_thread(save_runtime_config, message, load_config())
            self.runtime_manager.reload_config()
            await self._send(websocket, result)
            await self._send(websocket, await collect_status(self.config))
            return

        if message_type == "refresh_events":
            await self._send(websocket, {
                "type": "sidecar_events",
                "items": self.event_hub.recent_events(limit=20),
            })
            return

        if message_type == "refresh_notes":
            await self.broadcast({"type": "notes_changed", "reason": "manual_refresh"})
            return

        if message_type in {
            "start_listen",
            "stop_listen",
            "toggle_listen",
            "abort",
            "abort_speaking",
        }:
            await self._handle_control_message(websocket, message)
            return

        if message_type in {
            "start_py_xiaozhi",
            "stop_py_xiaozhi",
            "restart_py_xiaozhi",
        }:
            await self._handle_runtime_message(websocket, message)
            return

        await self._send(websocket, {
            "type": "error",
            "message": f"Unknown message type: {message_type}",
        })

    async def _handle_control_message(self, websocket: WebSocketServerProtocol, message: dict[str, Any]) -> None:
        raw_type = str(message.get("type", ""))
        command_name = "abort" if raw_type == "abort_speaking" else raw_type

        command = await self.control_hub.publish({
            "command": command_name,
            "source": "pc_app.websocket",
            "mode": message.get("mode", "manual"),
            "request_id": message.get("request_id", ""),
        })

        await self.event_hub.publish({
            "type": "assistant_control",
            "source": "pc_app.websocket",
            "command": command_name,
            "command_id": command.get("command_id"),
            "message": f"收到语音控制命令：{command_name}",
            "data": command,
        })

        await self._send(websocket, {
            "type": "control_accepted",
            "command": command_name,
            "command_id": command.get("command_id"),
            "message": f"Sidecar 已接收语音控制命令：{command_name}",
        })

    async def _handle_runtime_message(self, websocket: WebSocketServerProtocol, message: dict[str, Any]) -> None:
        message_type = str(message.get("type", ""))
        mode = str(message.get("mode", "") or "")

        await self._send(websocket, {
            "type": "runtime_action_accepted",
            "action": message_type,
            "message": f"Sidecar 已接收 py-xiaozhi 运行时操作：{message_type}",
        })

        try:
            self.runtime_manager.reload_config()

            # Phase 8.8.3:
            # Clear stale PC App voice controls before changing runtime lifecycle.
            # Otherwise, commands queued while py-xiaozhi was stopped can be replayed
            # by the next py-xiaozhi process as soon as PCBridge starts polling.
            cleared_control_commands = 0
            try:
                cleared_control_commands = self.control_hub.clear()
            except Exception:
                logger.debug("Failed to clear control queue before runtime action", exc_info=True)

            if cleared_control_commands:
                await self.event_hub.publish({
                    "type": "runtime_control_queue_cleared",
                    "source": "sidecar.runtime_manager",
                    "action": message_type,
                    "cleared": cleared_control_commands,
                    "message": f"已清空 {cleared_control_commands} 条过期语音控制命令",
                })

            if message_type == "start_py_xiaozhi":
                result = await asyncio.to_thread(self.runtime_manager.start, mode or None)
            elif message_type == "stop_py_xiaozhi":
                result = await asyncio.to_thread(self.runtime_manager.stop)
            elif message_type == "restart_py_xiaozhi":
                result = await asyncio.to_thread(self.runtime_manager.restart, mode or None)
            else:
                result = {
                    "ok": False,
                    "action": message_type,
                    "message": f"未知 py-xiaozhi 运行时操作：{message_type}",
                }
        except Exception as exc:
            result = {
                "ok": False,
                "action": message_type,
                "message": f"py-xiaozhi 运行时操作失败：{exc}",
            }

        event = {
            "type": "runtime_action_result",
            "source": "sidecar.runtime_manager",
            "action": message_type,
            "success": bool(result.get("ok")),
            "message": result.get("message", ""),
            "data": result,
        }
        await self.event_hub.publish(event)
        await self._send(websocket, event)
        await self._send(websocket, await collect_status(self.config))

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

    async def _event_loop(self) -> None:
        queue = self.event_hub.subscribe()
        try:
            while True:
                event = await queue.get()
                logger.info("Broadcast sidecar event: %s", event.get("type"))
                await self.broadcast(event)
        finally:
            self.event_hub.unsubscribe(queue)

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

    async def _send(self, websocket: WebSocketServerProtocol, payload: dict[str, Any]) -> None:
        await websocket.send(json.dumps(payload, ensure_ascii=False))
