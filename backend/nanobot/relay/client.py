"""WebSocket client for connecting to the relay server."""

import asyncio
import json
import sys
import time

import websockets
from loguru import logger

from nanobot.config.schema import Config


class AuthenticationError(Exception):
    """Raised when relay authentication fails."""


class RelayClient:
    """Connects to relay server, receives commands, sends responses."""

    def __init__(self, config: Config, command_handler):
        self.config = config
        self.relay_url = config.relay.url
        self.token = config.relay.token
        self.device_id = config.device.get_id()
        self.device_name = config.device.get_name()
        self.platform = sys.platform  # "darwin", "linux", "win32"
        self.command_handler = command_handler
        self._ws = None
        self._running = False
        self._reconnect_delay = 1  # exponential backoff

    async def start(self):
        """Connect to relay and start listening. Auto-reconnects."""
        self._running = True
        while self._running:
            try:
                await self._connect()
            except AuthenticationError:
                logger.error("Relay authentication failed, stopping")
                self._running = False
                raise
            except Exception as e:
                logger.error(f"Relay connection failed: {e}")
                if self._running:
                    logger.info(f"Reconnecting in {self._reconnect_delay}s...")
                    await asyncio.sleep(self._reconnect_delay)
                    self._reconnect_delay = min(self._reconnect_delay * 2, 60)

    async def stop(self):
        """Disconnect from relay."""
        self._running = False
        if self._ws:
            await self._ws.close()

    async def _connect(self):
        """Establish WebSocket connection and run message loop."""
        url = f"{self.relay_url}/ws/device"
        async with websockets.connect(url) as ws:
            self._ws = ws
            self._reconnect_delay = 1  # reset on successful connect
            await self._authenticate()
            # Start heartbeat and message loop concurrently
            await asyncio.gather(
                self._heartbeat_loop(),
                self._message_loop()
            )

    async def _authenticate(self):
        """Send device:auth message and wait for response."""
        await self._send({
            "type": "device:auth",
            "token": self.token,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "platform": self.platform,
            "timestamp": int(time.time() * 1000)
        })
        response = await self._ws.recv()
        msg = json.loads(response)
        if msg["type"] == "auth:error":
            raise AuthenticationError(f"Relay auth failed: {msg.get('reason')}")
        logger.info(f"Connected to relay as '{self.device_id}'")

    async def _heartbeat_loop(self):
        """Send heartbeat every 30 seconds."""
        while self._running:
            await self._send({
                "type": "device:heartbeat",
                "device_id": self.device_id,
                "timestamp": int(time.time() * 1000)
            })
            await asyncio.sleep(30)

    async def _message_loop(self):
        """Listen for commands from relay and handle them."""
        async for raw in self._ws:
            msg = json.loads(raw)
            if msg["type"] == "command":
                asyncio.create_task(self._handle_command(msg))

    async def _handle_command(self, msg: dict):
        """Process a command and send response back."""
        request_id = msg["request_id"]
        try:
            result = await self.command_handler.handle(msg["action"], msg.get("payload", {}))
            await self._send({
                "type": "response",
                "request_id": request_id,
                "device_id": self.device_id,
                "success": True,
                "data": result,
                "timestamp": int(time.time() * 1000)
            })
        except Exception as e:
            logger.error(f"Command '{msg.get('action')}' failed: {e}")
            await self._send({
                "type": "response",
                "request_id": request_id,
                "device_id": self.device_id,
                "success": False,
                "error": str(e),
                "timestamp": int(time.time() * 1000)
            })

    async def _send(self, msg: dict):
        """Send a JSON message over WebSocket."""
        if self._ws:
            await self._ws.send(json.dumps(msg))
