"""HTTP server for TMA monitoring and Worker Agent."""

import asyncio
import base64
import json
import mimetypes
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional
from datetime import datetime
from collections import deque

from aiohttp import web
from loguru import logger

from nanobot.monitor.activity import activity_log
from nanobot.monitor.auth import TelegramAuth, AuthResult

# Initialize mimetypes
mimetypes.init()


class WorkerAgent:
    """
    Worker Agent for TMA - handles direct commands and AI tasks.
    Shares context with the Chat Agent (Telegram).
    """

    def __init__(self):
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._response_queue: asyncio.Queue = asyncio.Queue()
        self._terminal_history: deque = deque(maxlen=500)
        self._shared_context: list[dict] = []  # Shared with Chat Agent
        self._ai_callback: Callable | None = None
        self._working_dir = str(Path.home() / ".nanobot" / "workspace")
        self._current_project_path: str | None = None  # Current project folder

    def set_ai_callback(self, callback: Callable[[str], Coroutine[Any, Any, str]]):
        """Set the AI processing callback."""
        self._ai_callback = callback

    async def execute_shell(self, command: str) -> dict:
        """Execute a shell command and return result."""
        start_time = time.time()

        # Log to terminal history
        self._add_terminal_entry("input", f"$ {command}")

        try:
            # Run command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._working_dir
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=60.0
            )

            output = stdout.decode('utf-8', errors='replace')
            error = stderr.decode('utf-8', errors='replace')

            duration = time.time() - start_time

            result = {
                "success": process.returncode == 0,
                "exit_code": process.returncode,
                "stdout": output,
                "stderr": error,
                "duration": round(duration, 2)
            }

            # Log output to terminal history
            if output.strip():
                self._add_terminal_entry("output", output.strip())
            if error.strip():
                self._add_terminal_entry("error", error.strip())

            # Add to shared context
            self._add_to_context("shell", command, result)

            return result

        except asyncio.TimeoutError:
            self._add_terminal_entry("error", "Command timed out (60s)")
            return {"success": False, "error": "Command timed out", "stdout": "", "stderr": ""}
        except Exception as e:
            self._add_terminal_entry("error", str(e))
            return {"success": False, "error": str(e), "stdout": "", "stderr": ""}

    async def process_ai_message(self, message: str) -> str:
        """Send message to AI and get response."""
        self._add_terminal_entry("user", message)

        if self._ai_callback:
            try:
                response = await self._ai_callback(message)
                self._add_terminal_entry("assistant", response)
                self._add_to_context("ai", message, {"response": response})
                return response
            except Exception as e:
                error_msg = f"AI Error: {str(e)}"
                self._add_terminal_entry("error", error_msg)
                return error_msg
        else:
            return "AI not connected"

    def _add_terminal_entry(self, entry_type: str, content: str):
        """Add entry to terminal history."""
        entry = {
            "type": entry_type,
            "content": content,
            "timestamp": time.time()
        }
        self._terminal_history.append(entry)

    def _add_to_context(self, action_type: str, input_data: str, result: dict):
        """Add action to shared context."""
        self._shared_context.append({
            "source": "tma_worker",
            "type": action_type,
            "input": input_data,
            "result": result,
            "timestamp": time.time()
        })
        # Keep last 50 context items
        if len(self._shared_context) > 50:
            self._shared_context = self._shared_context[-50:]

    def get_terminal_history(self, limit: int = 100) -> list[dict]:
        """Get terminal history."""
        return list(self._terminal_history)[-limit:]

    def get_shared_context(self) -> list[dict]:
        """Get shared context for Chat Agent."""
        return self._shared_context.copy()

    def add_from_chat_agent(self, message: str, response: str):
        """Add context from Chat Agent."""
        self._shared_context.append({
            "source": "chat_agent",
            "type": "conversation",
            "input": message,
            "result": {"response": response},
            "timestamp": time.time()
        })

    def set_working_dir(self, path: str):
        """Set working directory for shell commands."""
        if os.path.isdir(path):
            self._working_dir = path
            return True
        return False

    def clear_terminal(self):
        """Clear terminal history."""
        self._terminal_history.clear()

    def save_project_session(self) -> bool:
        """Save current terminal history to project folder."""
        if not self._current_project_path:
            return False

        try:
            session_file = Path(self._current_project_path) / ".nanobot_session.json"
            history_list = list(self._terminal_history)
            session_data = {
                "terminal_history": history_list,
                "saved_at": time.time()
            }
            session_file.write_text(json.dumps(session_data, ensure_ascii=False, indent=2))
            logger.debug(f"Saved session to {session_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save project session: {e}")
            return False

    def load_project_session(self, project_path: str) -> bool:
        """Load terminal history from project folder."""
        try:
            session_file = Path(project_path) / ".nanobot_session.json"
            if session_file.exists():
                session_data = json.loads(session_file.read_text(encoding="utf-8"))
                history_list = session_data.get("terminal_history", [])
                self._terminal_history.clear()
                for entry in history_list:
                    self._terminal_history.append(entry)
                logger.debug(f"Loaded session from {session_file}: {len(history_list)} entries")
            else:
                # New project, start fresh
                self._terminal_history.clear()
            self._current_project_path = project_path
            return True
        except Exception as e:
            logger.error(f"Failed to load project session: {e}")
            self._terminal_history.clear()
            self._current_project_path = project_path
            return False

    def switch_project(self, project_path: str) -> bool:
        """Switch to a different project, saving current and loading new session."""
        # Save current session
        if self._current_project_path:
            self.save_project_session()

        # Load new project session
        success = self.load_project_session(project_path)

        # Update working directory
        if os.path.isdir(project_path):
            self._working_dir = project_path

        return success


# Global worker agent instance
worker_agent = WorkerAgent()


class MonitorServer:
    """
    HTTP server for Telegram Mini App.

    Serves:
    - GET /api/status - Current bot status
    - GET /api/activities - Recent activities
    - GET /api/files - Browse files
    - GET /api/file - Read file content
    - GET / - TMA frontend

    Security:
    - All /api/* endpoints require valid Telegram initData
    - initData is validated using HMAC-SHA256 with bot token
    - User must be in allow_from list (if configured)
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 18791):
        self.host = host
        self.port = port
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

        # Authentication
        self._auth: Optional[TelegramAuth] = None
        self._auth_enabled: bool = False

        # Projects folder
        self._projects_root = Path.home() / "Desktop" / "Nanoprojects"
        self._current_project: str | None = None

        # Allowed root paths for security
        self._allowed_roots = [
            Path.home() / "Desktop",
            Path.home() / "Documents",
            Path.home() / "Downloads",
            Path.home() / ".nanobot",
            self._projects_root,
        ]

    def configure_auth(self, bot_token: str, allow_from: list[str] = None) -> None:
        """
        Configure Telegram authentication.

        Args:
            bot_token: Telegram bot token from BotFather
            allow_from: List of allowed user IDs or usernames
        """
        if bot_token:
            self._auth = TelegramAuth(bot_token, allow_from or [])
            self._auth_enabled = True
            logger.info(f"TMA auth enabled. Allowed users: {allow_from or 'all authenticated'}")

    async def start(self) -> None:
        """Start the HTTP server."""
        self._app = web.Application(client_max_size=10 * 1024 * 1024)

        # Store auth reference for middleware
        auth = self._auth
        auth_enabled = self._auth_enabled

        # CORS middleware
        @web.middleware
        async def cors_middleware(request: web.Request, handler):
            if request.method == "OPTIONS":
                response = web.Response()
            else:
                response = await handler(request)

            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Telegram-Init-Data"
            return response

        # Authentication middleware
        @web.middleware
        async def auth_middleware(request: web.Request, handler):
            # Skip auth for static files and TMA frontend
            path = request.path
            if not path.startswith("/api/"):
                return await handler(request)

            # If auth not configured, allow all (development mode)
            if not auth_enabled or not auth:
                logger.warning(f"Auth not configured - allowing unauthenticated access to {path}")
                return await handler(request)

            # Get initData from header
            init_data = request.headers.get("X-Telegram-Init-Data", "")

            if not init_data:
                logger.warning(f"Missing initData for {path}")
                return web.json_response(
                    {"error": "Authentication required", "code": "AUTH_REQUIRED"},
                    status=401
                )

            # Validate initData
            result = auth.validate(init_data)

            if not result.valid:
                logger.warning(f"Auth failed for {path}: {result.error}")
                return web.json_response(
                    {"error": result.error, "code": "AUTH_FAILED"},
                    status=403
                )

            # Store user in request for handlers
            request["tg_user"] = result.user

            return await handler(request)

        self._app.middlewares.append(cors_middleware)
        self._app.middlewares.append(auth_middleware)

        # Routes
        self._app.router.add_get("/", self._serve_tma)
        self._app.router.add_get("/api/status", self._get_status)
        self._app.router.add_get("/api/activities", self._get_activities)
        self._app.router.add_post("/api/clear", self._clear_activities)
        # File browser
        self._app.router.add_get("/api/files", self._list_files)
        self._app.router.add_get("/api/file", self._read_file)
        self._app.router.add_get("/api/roots", self._get_roots)
        # Media preview & transfer
        self._app.router.add_get("/api/media", self._serve_media)
        self._app.router.add_post("/api/send-to-chat", self._send_to_chat)

        # Worker Agent / Terminal API
        self._app.router.add_post("/api/terminal/exec", self._terminal_exec)
        self._app.router.add_post("/api/terminal/ai", self._terminal_ai)
        self._app.router.add_get("/api/terminal/history", self._terminal_history)
        self._app.router.add_post("/api/terminal/clear", self._terminal_clear)
        self._app.router.add_post("/api/terminal/cd", self._terminal_cd)
        self._app.router.add_get("/api/context/shared", self._get_shared_context)

        # Projects API
        self._app.router.add_get("/api/projects", self._list_projects)
        self._app.router.add_post("/api/projects/create", self._create_project)
        self._app.router.add_post("/api/projects/select", self._select_project)
        self._app.router.add_get("/api/projects/current", self._get_current_project)
        self._app.router.add_post("/api/terminal/new-chat", self._new_chat)

        # Static files (TMA directory)
        tma_dir = Path(__file__).parent / "tma"
        if tma_dir.exists():
            self._app.router.add_static("/static/", tma_dir, name="tma_static")
            # Logo direct route
            self._app.router.add_get("/logo.png", self._serve_logo)
            # Also serve any .html files directly
            self._app.router.add_get("/{filename}.html", self._serve_tma_file)

        # Start server
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()

        logger.info(f"Monitor server started at http://{self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the HTTP server."""
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()
        logger.info("Monitor server stopped")

    async def _serve_tma(self, request: web.Request) -> web.Response:
        """Serve the TMA frontend."""
        tma_path = Path(__file__).parent / "tma" / "index.html"

        if not tma_path.exists():
            return web.Response(
                text="TMA not found. Run setup first.",
                status=404
            )

        return web.FileResponse(tma_path)

    async def _serve_tma_file(self, request: web.Request) -> web.Response:
        """Serve any HTML file from TMA directory."""
        filename = request.match_info.get("filename", "index")
        tma_path = Path(__file__).parent / "tma" / f"{filename}.html"

        if not tma_path.exists():
            return web.Response(
                text=f"File {filename}.html not found.",
                status=404
            )

        return web.FileResponse(tma_path)

    async def _serve_logo(self, request: web.Request) -> web.Response:
        """Serve the TMA logo."""
        logo_path = Path(__file__).parent / "tma" / "nanobots_tma_logo.png"
        if not logo_path.exists():
            return web.Response(text="Logo not found", status=404)
        return web.FileResponse(logo_path, headers={"Content-Type": "image/png"})

    async def _get_status(self, request: web.Request) -> web.Response:
        """Get current bot status."""
        status = activity_log.get_status()
        return web.json_response(status)

    async def _get_activities(self, request: web.Request) -> web.Response:
        """Get recent activities."""
        limit = int(request.query.get("limit", 50))
        activities = activity_log.get_recent(limit)
        return web.json_response({
            "activities": activities,
            "status": activity_log.get_status()
        })

    async def _clear_activities(self, request: web.Request) -> web.Response:
        """Clear activity log."""
        activity_log.clear()
        return web.json_response({"ok": True})

    async def _get_roots(self, request: web.Request) -> web.Response:
        """Get available root directories."""
        roots = []
        for root in self._allowed_roots:
            if root.exists():
                roots.append({
                    "path": str(root),
                    "name": root.name,
                    "icon": self._get_folder_icon(root.name)
                })
        return web.json_response({"roots": roots})

    def _get_folder_icon(self, name: str) -> str:
        """Get icon for folder."""
        icons = {
            "Desktop": "🖥️",
            "Documents": "📄",
            "Downloads": "⬇️",
            ".nanobot": "🤖",
        }
        return icons.get(name, "📁")

    def _is_path_allowed(self, path: Path) -> bool:
        """Check if path is within allowed roots."""
        try:
            resolved = path.resolve()
            for root in self._allowed_roots:
                if root.exists():
                    try:
                        resolved.relative_to(root.resolve())
                        return True
                    except ValueError:
                        continue
            return False
        except Exception:
            return False

    async def _list_files(self, request: web.Request) -> web.Response:
        """List files in directory."""
        path_str = request.query.get("path", "")

        if not path_str:
            # Return roots
            return await self._get_roots(request)

        path = Path(path_str)

        if not self._is_path_allowed(path):
            return web.json_response({"error": "Access denied"}, status=403)

        if not path.exists():
            return web.json_response({"error": "Path not found"}, status=404)

        if not path.is_dir():
            return web.json_response({"error": "Not a directory"}, status=400)

        files = []
        try:
            for item in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                try:
                    stat = item.stat()
                    files.append({
                        "name": item.name,
                        "path": str(item),
                        "is_dir": item.is_dir(),
                        "size": stat.st_size if not item.is_dir() else None,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "ext": item.suffix.lower() if not item.is_dir() else None,
                        "icon": self._get_file_icon(item)
                    })
                except (PermissionError, OSError):
                    continue
        except PermissionError:
            return web.json_response({"error": "Permission denied"}, status=403)

        return web.json_response({
            "path": str(path),
            "parent": str(path.parent) if path.parent != path else None,
            "files": files
        })

    def _get_file_icon(self, path: Path) -> str:
        """Get icon for file based on extension."""
        if path.is_dir():
            return "📁"

        ext = path.suffix.lower()
        icons = {
            ".py": "🐍",
            ".js": "📜",
            ".ts": "📘",
            ".html": "🌐",
            ".css": "🎨",
            ".json": "📋",
            ".md": "📝",
            ".txt": "📄",
            ".jpg": "🖼️", ".jpeg": "🖼️", ".png": "🖼️", ".gif": "🖼️",
            ".mp3": "🎵", ".wav": "🎵", ".ogg": "🎵",
            ".mp4": "🎬", ".avi": "🎬", ".mkv": "🎬",
            ".pdf": "📕",
            ".zip": "📦", ".rar": "📦", ".7z": "📦",
            ".exe": "⚙️",
            ".bat": "⚙️", ".cmd": "⚙️", ".ps1": "⚙️",
        }
        return icons.get(ext, "📄")

    async def _read_file(self, request: web.Request) -> web.Response:
        """Read file content."""
        path_str = request.query.get("path", "")

        if not path_str:
            return web.json_response({"error": "Path required"}, status=400)

        path = Path(path_str)

        if not self._is_path_allowed(path):
            return web.json_response({"error": "Access denied"}, status=403)

        if not path.exists():
            return web.json_response({"error": "File not found"}, status=404)

        if path.is_dir():
            return web.json_response({"error": "Cannot read directory"}, status=400)

        # Check file size (max 1MB for preview)
        try:
            size = path.stat().st_size
            if size > 1024 * 1024:
                return web.json_response({
                    "path": str(path),
                    "size": size,
                    "preview": False,
                    "message": "File too large for preview"
                })
        except OSError:
            return web.json_response({"error": "Cannot read file"}, status=500)

        # Try to read as text
        try:
            content = path.read_text(encoding="utf-8")
            return web.json_response({
                "path": str(path),
                "content": content,
                "size": size,
                "type": "text"
            })
        except UnicodeDecodeError:
            # Binary file
            return web.json_response({
                "path": str(path),
                "size": size,
                "type": "binary",
                "message": "Binary file - cannot preview"
            })
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def _serve_media(self, request: web.Request) -> web.Response:
        """Serve media files (images, videos, HTML) for preview."""
        path_str = request.query.get("path", "")

        if not path_str:
            return web.json_response({"error": "Path required"}, status=400)

        path = Path(path_str)

        if not self._is_path_allowed(path):
            return web.json_response({"error": "Access denied"}, status=403)

        if not path.exists():
            return web.json_response({"error": "File not found"}, status=404)

        if path.is_dir():
            return web.json_response({"error": "Cannot serve directory"}, status=400)

        # Get MIME type
        mime_type, _ = mimetypes.guess_type(str(path))
        if not mime_type:
            mime_type = "application/octet-stream"

        # Check file size (max 50MB for media)
        try:
            size = path.stat().st_size
            if size > 50 * 1024 * 1024:
                return web.json_response({
                    "error": "File too large (max 50MB)"
                }, status=413)
        except OSError:
            return web.json_response({"error": "Cannot read file"}, status=500)

        # Serve the file
        return web.FileResponse(
            path,
            headers={
                "Content-Type": mime_type,
                "Cache-Control": "max-age=3600"
            }
        )

    async def _send_to_chat(self, request: web.Request) -> web.Response:
        """Send a file to the Telegram chat."""
        try:
            data = await request.json()
            file_path = data.get("path")
            chat_id = data.get("chat_id")
            caption = data.get("caption", "")

            if not file_path:
                return web.json_response({"error": "path required"}, status=400)

            path = Path(file_path)

            if not self._is_path_allowed(path):
                return web.json_response({"error": "Access denied"}, status=403)

            if not path.exists():
                return web.json_response({"error": "File not found"}, status=404)

            # Check file size (max 50MB for Telegram)
            size = path.stat().st_size
            if size > 50 * 1024 * 1024:
                return web.json_response({
                    "error": "File too large for Telegram (max 50MB)"
                }, status=413)

            # Queue file for sending via the message bus
            from nanobot.bus.events import OutboundMessage
            from nanobot.bus.queue import MessageBus

            # Store pending file transfer
            if not hasattr(self, '_pending_transfers'):
                self._pending_transfers = []

            transfer = {
                "path": str(path),
                "chat_id": chat_id,
                "caption": caption,
                "filename": path.name,
                "size": size,
                "mime_type": mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            }
            self._pending_transfers.append(transfer)

            logger.info(f"File transfer queued: {path.name} -> chat {chat_id}")

            return web.json_response({
                "ok": True,
                "message": f"File '{path.name}' queued for transfer",
                "transfer": transfer
            })

        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON"}, status=400)
        except Exception as e:
            logger.error(f"Send to chat error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    def get_pending_transfers(self) -> list:
        """Get and clear pending file transfers."""
        if not hasattr(self, '_pending_transfers'):
            return []
        transfers = self._pending_transfers.copy()
        self._pending_transfers.clear()
        return transfers

    # ========== Worker Agent / Terminal API ==========

    async def _terminal_exec(self, request: web.Request) -> web.Response:
        """Execute shell command from TMA terminal."""
        try:
            data = await request.json()
            command = data.get("command", "").strip()

            if not command:
                return web.json_response({"error": "Command required"}, status=400)

            # Security: block dangerous commands
            dangerous = ["rm -rf /", "format", "del /s /q c:\\", ":(){ :|:& };:"]
            if any(d in command.lower() for d in dangerous):
                return web.json_response({"error": "Command blocked for safety"}, status=403)

            result = await worker_agent.execute_shell(command)
            return web.json_response(result)

        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON"}, status=400)
        except Exception as e:
            logger.error(f"Terminal exec error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _terminal_ai(self, request: web.Request) -> web.Response:
        """Send message to Worker AI agent."""
        try:
            data = await request.json()
            message = data.get("message", "").strip()

            if not message:
                return web.json_response({"error": "Message required"}, status=400)

            # Get activity count before processing to track new actions
            activities_before = activity_log.get_recent(100)
            count_before = len(activities_before)

            response = await worker_agent.process_ai_message(message)

            # Get new activities (tool calls, etc.) that happened during processing
            activities_after = activity_log.get_recent(100)
            new_activities = activities_after[count_before:] if len(activities_after) > count_before else []

            # Convert activities to actions format for TMA
            actions = []
            for act in new_activities:
                act_type = act.get("type", "")
                content = act.get("content", "")
                metadata = act.get("metadata", {})

                if act_type == "tool_call":
                    tool_name = metadata.get("tool", "Tool")

                    # Map tool names to frontend action types
                    if tool_name == "exec":
                        action_type = "command"
                        title = "Executing"
                    elif tool_name == "read_file":
                        action_type = "read"
                        title = "Reading"
                    elif tool_name == "write_file":
                        action_type = "edit"
                        title = "Writing"
                    elif tool_name == "edit_file":
                        action_type = "edit"
                        title = "Editing"
                    elif tool_name == "list_dir":
                        action_type = "read"
                        title = "Listing"
                    elif tool_name == "web_search":
                        action_type = "search"
                        title = "Searching"
                    elif tool_name == "web_fetch":
                        action_type = "search"
                        title = "Fetching"
                    else:
                        action_type = "tool"
                        title = tool_name

                    actions.append({
                        "type": action_type,
                        "tool": title,
                        "content": content,
                        "status": "running"
                    })

                elif act_type == "tool_result":
                    success = metadata.get("success", True)
                    # Update last action with result
                    if actions and actions[-1].get("status") == "running":
                        actions[-1]["status"] = "done" if success else "error"
                        actions[-1]["result"] = content[:300] if content else ""

                elif act_type == "thinking":
                    actions.append({
                        "type": "thinking",
                        "content": content
                    })

            return web.json_response({
                "ok": True,
                "response": response,
                "actions": actions
            })

        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON"}, status=400)
        except Exception as e:
            logger.error(f"Terminal AI error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _terminal_history(self, request: web.Request) -> web.Response:
        """Get terminal history."""
        limit = int(request.query.get("limit", 100))
        history = worker_agent.get_terminal_history(limit)
        return web.json_response({
            "history": history,
            "working_dir": worker_agent._working_dir
        })

    async def _terminal_clear(self, request: web.Request) -> web.Response:
        """Clear terminal history."""
        worker_agent.clear_terminal()
        return web.json_response({"ok": True})

    async def _new_chat(self, request: web.Request) -> web.Response:
        """Start a new chat session (clear history, keep project)."""
        # Clear terminal history
        worker_agent.clear_terminal()

        # Save empty session if in a project
        if worker_agent._current_project_path:
            worker_agent.save_project_session()

        return web.json_response({
            "ok": True,
            "project": self._current_project
        })

    async def _terminal_cd(self, request: web.Request) -> web.Response:
        """Change working directory."""
        try:
            data = await request.json()
            path = data.get("path", "").strip()

            if not path:
                return web.json_response({"error": "Path required"}, status=400)

            # Expand ~ and resolve
            expanded = os.path.expanduser(path)
            if not os.path.isabs(expanded):
                expanded = os.path.join(worker_agent._working_dir, expanded)
            expanded = os.path.normpath(expanded)

            if worker_agent.set_working_dir(expanded):
                return web.json_response({
                    "ok": True,
                    "working_dir": expanded
                })
            else:
                return web.json_response({"error": "Directory not found"}, status=404)

        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def _get_shared_context(self, request: web.Request) -> web.Response:
        """Get shared context between agents."""
        context = worker_agent.get_shared_context()
        return web.json_response({"context": context})

    # ========== Projects API ==========

    async def _list_projects(self, request: web.Request) -> web.Response:
        """List all projects in Nanoprojects folder."""
        try:
            # Ensure projects root exists
            if not self._projects_root.exists():
                self._projects_root.mkdir(parents=True, exist_ok=True)

            projects = []
            for item in sorted(self._projects_root.iterdir()):
                if item.is_dir() and not item.name.startswith('.'):
                    try:
                        stat = item.stat()
                        projects.append({
                            "name": item.name,
                            "path": str(item),
                            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            "is_current": item.name == self._current_project
                        })
                    except OSError:
                        continue

            return web.json_response({
                "projects": projects,
                "current": self._current_project,
                "root": str(self._projects_root)
            })

        except Exception as e:
            logger.error(f"List projects error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _create_project(self, request: web.Request) -> web.Response:
        """Create a new project folder."""
        try:
            data = await request.json()
            name = data.get("name", "").strip()

            if not name:
                return web.json_response({"error": "Project name required"}, status=400)

            # Sanitize name (remove dangerous characters)
            safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
            if not safe_name:
                return web.json_response({"error": "Invalid project name"}, status=400)

            # Create project folder
            project_path = self._projects_root / safe_name

            if project_path.exists():
                return web.json_response({"error": "Project already exists"}, status=409)

            project_path.mkdir(parents=True, exist_ok=True)

            # Auto-select the new project (saves old session if any)
            self._current_project = safe_name
            worker_agent.switch_project(str(project_path))

            logger.info(f"Created project: {safe_name}")

            return web.json_response({
                "ok": True,
                "name": safe_name,
                "path": str(project_path)
            })

        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON"}, status=400)
        except Exception as e:
            logger.error(f"Create project error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _select_project(self, request: web.Request) -> web.Response:
        """Select a project and switch working context."""
        try:
            data = await request.json()
            name = data.get("name", "").strip()

            if not name:
                return web.json_response({"error": "Project name required"}, status=400)

            project_path = self._projects_root / name

            if not project_path.exists() or not project_path.is_dir():
                return web.json_response({"error": "Project not found"}, status=404)

            # Switch to this project (saves old session, loads new)
            self._current_project = name
            worker_agent.switch_project(str(project_path))

            logger.info(f"Selected project: {name}")

            return web.json_response({
                "ok": True,
                "name": name,
                "path": str(project_path)
            })

        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON"}, status=400)
        except Exception as e:
            logger.error(f"Select project error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _get_current_project(self, request: web.Request) -> web.Response:
        """Get currently selected project."""
        if self._current_project:
            project_path = self._projects_root / self._current_project
            return web.json_response({
                "name": self._current_project,
                "path": str(project_path),
                "exists": project_path.exists()
            })
        else:
            return web.json_response({
                "name": None,
                "path": None,
                "exists": False
            })


# Global instances
monitor_server = MonitorServer()
