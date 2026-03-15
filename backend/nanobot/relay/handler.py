"""Command handler for relay — bridges relay commands to existing functionality."""

import os
import platform
import sys
import time
from datetime import datetime
from pathlib import Path

from loguru import logger

from nanobot.config.schema import Config


class CommandHandler:
    """Handles commands received from TMA via relay."""

    def __init__(self, config: Config, worker_agent):
        self.config = config
        self.worker = worker_agent  # existing WorkerAgent from monitor
        self._start_time = time.time()
        self._projects_root = Path.home() / "Desktop" / "Nanoprojects"

    async def handle(self, action: str, payload: dict) -> dict:
        """Route action to appropriate handler. Returns response data dict."""
        handlers = {
            "chat": self._handle_chat,
            "exec": self._handle_exec,
            "files:list": self._handle_files_list,
            "files:read": self._handle_files_read,
            "files:roots": self._handle_files_roots,
            "status": self._handle_status,
            "projects:list": self._handle_projects_list,
            "projects:create": self._handle_projects_create,
            "projects:select": self._handle_projects_select,
        }
        handler = handlers.get(action)
        if not handler:
            raise ValueError(f"Unknown action: {action}")
        return await handler(payload)

    async def _handle_chat(self, payload: dict) -> dict:
        """Send message to AI agent. Reuses WorkerAgent.process_ai_message."""
        content = payload.get("content", "")
        if not content:
            raise ValueError("Message content required")
        response = await self.worker.process_ai_message(content)
        return {"content": response}

    async def _handle_exec(self, payload: dict) -> dict:
        """Execute shell command. Reuses WorkerAgent.execute_shell."""
        command = payload.get("command", "").strip()
        if not command:
            raise ValueError("Command required")

        cwd = payload.get("cwd")
        if cwd:
            self.worker.set_working_dir(cwd)

        result = await self.worker.execute_shell(command)
        return {
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "exit_code": result.get("exit_code", -1),
        }

    async def _handle_files_list(self, payload: dict) -> dict:
        """List directory contents."""
        path_str = payload.get("path", "")
        if not path_str:
            raise ValueError("Path required")

        path = Path(path_str)
        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        if not path.is_dir():
            raise ValueError(f"Not a directory: {path}")

        entries = []
        for item in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            try:
                stat = item.stat()
                entries.append({
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size": stat.st_size if not item.is_dir() else 0,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat() + "Z",
                })
            except (PermissionError, OSError):
                continue

        return {"path": str(path), "entries": entries}

    async def _handle_files_read(self, payload: dict) -> dict:
        """Read file content."""
        path_str = payload.get("path", "")
        if not path_str:
            raise ValueError("Path required")

        path = Path(path_str)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if path.is_dir():
            raise ValueError("Cannot read directory")

        content = path.read_text(encoding="utf-8")
        return {
            "path": str(path),
            "content": content,
            "encoding": "utf-8",
        }

    async def _handle_files_roots(self, payload: dict) -> dict:
        """Get available root directories."""
        roots = [
            Path.home() / "Desktop",
            Path.home() / "Documents",
            Path.home() / "Downloads",
            Path.home() / ".nanobot",
            self._projects_root,
        ]
        return {
            "roots": [
                {"path": str(r), "name": r.name}
                for r in roots if r.exists()
            ]
        }

    async def _handle_status(self, payload: dict) -> dict:
        """Get device status."""
        return {
            "agent_status": "idle",
            "uptime_seconds": int(time.time() - self._start_time),
            "platform": sys.platform,
            "hostname": platform.node(),
            "python_version": platform.python_version(),
        }

    async def _handle_projects_list(self, payload: dict) -> dict:
        """List projects in Nanoprojects folder."""
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
                    })
                except OSError:
                    continue

        return {"projects": projects}

    async def _handle_projects_create(self, payload: dict) -> dict:
        """Create a new project folder."""
        name = payload.get("name", "").strip()
        if not name:
            raise ValueError("Project name required")

        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
        if not safe_name:
            raise ValueError("Invalid project name")

        project_path = self._projects_root / safe_name
        if project_path.exists():
            raise ValueError("Project already exists")

        project_path.mkdir(parents=True, exist_ok=True)
        self.worker.switch_project(str(project_path))

        return {"name": safe_name, "path": str(project_path)}

    async def _handle_projects_select(self, payload: dict) -> dict:
        """Select a project and switch working context."""
        name = payload.get("name", "").strip()
        if not name:
            raise ValueError("Project name required")

        project_path = self._projects_root / name
        if not project_path.exists() or not project_path.is_dir():
            raise FileNotFoundError(f"Project not found: {name}")

        self.worker.switch_project(str(project_path))

        return {"name": name, "path": str(project_path)}
