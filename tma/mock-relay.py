"""
Mock relay server for local TMA testing.
Simulates a relay with one online device that echoes commands back.

Usage: python mock-relay.py
Then open http://localhost:8080 in browser (or Telegram test mode).
"""

import asyncio
import json
import time
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import threading

try:
    import websockets
except ImportError:
    print("Installing websockets...")
    os.system("pip3 install websockets")
    import websockets

TMA_DIR = Path(__file__).parent
PORT_HTTP = 8080
PORT_WS = 8787
TOKEN = "test-token-for-local-dev"

MOCK_DEVICES = [
    {
        "device_id": "mock-macbook",
        "device_name": "MacBook Pro (mock)",
        "platform": "darwin",
        "status": "online",
        "connected_at": int(time.time() * 1000),
    },
    {
        "device_id": "mock-pc",
        "device_name": "Desktop PC (mock)",
        "platform": "win32",
        "status": "offline",
        "last_seen": int(time.time() * 1000) - 7200000,
    },
]


def now():
    return int(time.time() * 1000)


async def handle_client(ws):
    """Handle a TMA client WebSocket connection."""
    authenticated = False
    print(f"[WS] Client connected")

    try:
        async for raw in ws:
            msg = json.loads(raw)
            msg_type = msg.get("type")
            print(f"[WS] ← {msg_type}: {json.dumps(msg, ensure_ascii=False)[:200]}")

            if msg_type == "client:auth":
                if msg.get("token") == TOKEN:
                    authenticated = True
                    resp = {
                        "type": "auth:ok",
                        "devices": MOCK_DEVICES,
                        "timestamp": now(),
                    }
                    await ws.send(json.dumps(resp))
                    print(f"[WS] → auth:ok (sent {len(MOCK_DEVICES)} devices)")
                else:
                    await ws.send(json.dumps({
                        "type": "auth:error",
                        "reason": "invalid_token",
                        "timestamp": now(),
                    }))
                    print(f"[WS] → auth:error")
                    await ws.close()
                    return

            elif msg_type == "devices:list":
                await ws.send(json.dumps({
                    "type": "devices:status",
                    "devices": MOCK_DEVICES,
                    "timestamp": now(),
                }))

            elif msg_type == "command":
                if not authenticated:
                    continue

                device_id = msg.get("device_id")
                request_id = msg.get("request_id")
                action = msg.get("action")
                payload = msg.get("payload", {})

                # Check if target device is "online"
                device = next((d for d in MOCK_DEVICES if d["device_id"] == device_id), None)
                if not device or device["status"] == "offline":
                    await ws.send(json.dumps({
                        "type": "error",
                        "request_id": request_id,
                        "reason": "device_offline",
                        "device_id": device_id,
                        "timestamp": now(),
                    }))
                    continue

                # Simulate responses based on action
                response_data = await mock_response(action, payload)
                await ws.send(json.dumps({
                    "type": "response",
                    "request_id": request_id,
                    "device_id": device_id,
                    "success": True,
                    "data": response_data,
                    "timestamp": now(),
                }))
                print(f"[WS] → response for {action}")

    except websockets.exceptions.ConnectionClosed:
        print(f"[WS] Client disconnected")


async def mock_response(action, payload):
    """Generate mock responses for each action type."""

    if action == "status":
        return {
            "agent_status": "idle",
            "uptime_seconds": 3600,
            "platform": "darwin",
            "hostname": "MockBook-Pro.local",
            "python_version": "3.11.5",
        }

    elif action == "chat":
        content = payload.get("content", "")
        return {
            "content": f"[Mock response] You said: \"{content}\"\n\nI'm a simulated agent running locally for UI testing. In production, this would be processed by the AI agent on your computer."
        }

    elif action == "exec":
        command = payload.get("command", "")
        return {
            "stdout": f"$ {command}\n[mock output] Command would execute on remote device.\nExample output line 1\nExample output line 2",
            "stderr": "",
            "exit_code": 0,
        }

    elif action == "files:roots":
        return {
            "roots": [
                {"name": "Desktop", "path": "/Users/user/Desktop"},
                {"name": "Documents", "path": "/Users/user/Documents"},
                {"name": "Downloads", "path": "/Users/user/Downloads"},
            ]
        }

    elif action == "files:list":
        path = payload.get("path", "/Users/user")
        return {
            "path": path,
            "entries": [
                {"name": "project-alpha", "type": "directory", "size": 0, "modified": "2025-03-14T10:00:00Z"},
                {"name": "notes.md", "type": "file", "size": 2048, "modified": "2025-03-14T09:30:00Z"},
                {"name": "script.py", "type": "file", "size": 512, "modified": "2025-03-13T15:00:00Z"},
                {"name": "photo.png", "type": "file", "size": 1048576, "modified": "2025-03-12T12:00:00Z"},
                {"name": "data.csv", "type": "file", "size": 4096, "modified": "2025-03-11T08:00:00Z"},
            ]
        }

    elif action == "files:read":
        path = payload.get("path", "")
        return {
            "path": path,
            "content": f"# Mock file content\n\nThis is simulated content for:\n`{path}`\n\nLine 3\nLine 4\nLine 5\n",
            "encoding": "utf-8",
        }

    elif action == "projects:list":
        return {
            "projects": [
                {"name": "my-webapp", "active": True},
                {"name": "api-server", "active": False},
                {"name": "ml-pipeline", "active": False},
            ]
        }

    elif action == "projects:create":
        name = payload.get("name", "unnamed")
        return {"name": name, "created": True}

    elif action == "projects:select":
        name = payload.get("name", "")
        return {"name": name, "selected": True}

    else:
        return {"message": f"Unknown action: {action}"}


async def ws_server():
    """Start WebSocket server."""
    async with websockets.serve(handle_client, "localhost", PORT_WS):
        print(f"[WS] Mock relay running on ws://localhost:{PORT_WS}")
        await asyncio.Future()  # run forever


def http_server():
    """Start HTTP server for TMA files."""
    os.chdir(TMA_DIR)

    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            if ".html" in str(args) or ".js" in str(args):
                print(f"[HTTP] {args[0]}")

        def end_headers(self):
            # Allow embedding & CORS
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("X-Frame-Options", "ALLOWALL")
            super().end_headers()

    server = HTTPServer(("localhost", PORT_HTTP), Handler)
    print(f"[HTTP] TMA serving at http://localhost:{PORT_HTTP}")
    server.serve_forever()


def main():
    print("=" * 50)
    print("  Nanobots TMA — Local Test Server")
    print("=" * 50)
    print()
    print(f"  TMA:   http://localhost:{PORT_HTTP}")
    print(f"  Relay: ws://localhost:{PORT_WS}")
    print(f"  Token: {TOKEN}")
    print()
    print("  Update tma/config.js with:")
    print(f'    relayUrl: "ws://localhost:{PORT_WS}"')
    print(f'    relayToken: "{TOKEN}"')
    print()
    print("=" * 50)
    print()

    # Start HTTP server in a thread
    http_thread = threading.Thread(target=http_server, daemon=True)
    http_thread.start()

    # Start WebSocket server in asyncio
    try:
        asyncio.run(ws_server())
    except KeyboardInterrupt:
        print("\nShutting down.")


if __name__ == "__main__":
    main()
