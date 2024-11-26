import asyncio
import json
import logging
from typing import Dict, Set
import websockets

class WebSocketServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.server = None
        self.logger = logging.getLogger("telegram_classifier")

    async def register(self, websocket: websockets.WebSocketServerProtocol):
        self.clients.add(websocket)
        self.logger.info(f"New client connected. Total clients: {len(self.clients)}")

    async def unregister(self, websocket: websockets.WebSocketServerProtocol):
        self.clients.remove(websocket)
        self.logger.info(f"Client disconnected. Total clients: {len(self.clients)}")

    async def broadcast(self, message: dict):
        if not self.clients:
            self.logger.warning("No clients connected to broadcast message")
            return

        disconnected_clients = set()
        for client in self.clients:
            try:
                await client.send(json.dumps(message))
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.add(client)
            except Exception as e:
                self.logger.error(f"Error broadcasting message: {e}")
                disconnected_clients.add(client)

        # Remove disconnected clients
        for client in disconnected_clients:
            await self.unregister(client)

    async def handle_client(self, websocket: websockets.WebSocketServerProtocol):
        await self.register(websocket)
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    if data.get("type") == "health_check":
                        await websocket.send(json.dumps({"type": "health_check", "status": "healthy"}))
                except json.JSONDecodeError:
                    self.logger.error(f"Invalid JSON received: {message}")
                except Exception as e:
                    self.logger.error(f"Error handling message: {e}")
        finally:
            await self.unregister(websocket)

    async def start(self):
        self.server = await websockets.serve(self.handle_client, self.host, self.port)
        self.logger.info(f"WebSocket server started on ws://{self.host}:{self.port}")

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.logger.info("WebSocket server stopped") 