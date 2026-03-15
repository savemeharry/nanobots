"""Activity logging for TMA monitoring."""

import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any
from collections import deque
from threading import Lock


class ActivityType(str, Enum):
    """Type of activity."""
    MESSAGE_IN = "message_in"      # Incoming message from user
    MESSAGE_OUT = "message_out"    # Outgoing response to user
    TOOL_CALL = "tool_call"        # Tool was called
    TOOL_RESULT = "tool_result"    # Tool returned result
    ERROR = "error"                # Error occurred
    THINKING = "thinking"          # Agent is processing


@dataclass
class Activity:
    """Single activity record."""
    id: str
    type: ActivityType
    timestamp: float
    channel: str = ""
    content: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value
        return d


class ActivityLog:
    """
    Thread-safe activity log with fixed-size buffer.

    Stores recent activities in memory for TMA to display.
    """

    _instance = None
    _lock = Lock()

    def __new__(cls, max_size: int = 100):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, max_size: int = 100):
        if self._initialized:
            return

        self._activities: deque[Activity] = deque(maxlen=max_size)
        self._counter = 0
        self._current_task: str | None = None
        self._status = "idle"
        self._initialized = True

    def _next_id(self) -> str:
        self._counter += 1
        return f"act_{self._counter}"

    def log(
        self,
        activity_type: ActivityType,
        content: str = "",
        channel: str = "",
        metadata: dict | None = None
    ) -> Activity:
        """Log an activity."""
        activity = Activity(
            id=self._next_id(),
            type=activity_type,
            timestamp=time.time(),
            channel=channel,
            content=content[:500],  # Truncate long content
            metadata=metadata or {}
        )

        with self._lock:
            self._activities.append(activity)

        return activity

    def message_in(self, content: str, channel: str, sender: str = "") -> Activity:
        """Log incoming message."""
        self._status = "processing"
        self._current_task = content[:100]
        return self.log(
            ActivityType.MESSAGE_IN,
            content=content,
            channel=channel,
            metadata={"sender": sender}
        )

    def message_out(self, content: str, channel: str) -> Activity:
        """Log outgoing message."""
        self._status = "idle"
        self._current_task = None
        return self.log(
            ActivityType.MESSAGE_OUT,
            content=content,
            channel=channel
        )

    def tool_call(self, tool_name: str, args: dict, channel: str = "") -> Activity:
        """Log tool call with full command details."""
        self._status = f"executing: {tool_name}"

        # Build detailed content showing what will be executed
        if tool_name == "exec" and "command" in args:
            content = f"$ {args['command']}"
        else:
            content = f"{tool_name}: {args}"

        return self.log(
            ActivityType.TOOL_CALL,
            content=content[:1000],  # Show more of the command
            channel=channel,
            metadata={"tool": tool_name, "args": args}
        )

    def tool_result(self, tool_name: str, result: str, success: bool = True) -> Activity:
        """Log tool result with full output."""
        # Interpret empty/no output
        display_result = result
        if result == "(no output)" or not result.strip():
            display_result = "OK (command executed, no output)"
            success = True
        elif result.startswith("Error"):
            success = False

        return self.log(
            ActivityType.TOOL_RESULT,
            content=display_result[:1000],  # Show more of the result
            metadata={"tool": tool_name, "success": success, "raw_length": len(result)}
        )

    def error(self, error: str, context: str = "") -> Activity:
        """Log error."""
        self._status = "error"
        return self.log(
            ActivityType.ERROR,
            content=error,
            metadata={"context": context}
        )

    def thinking(self, message: str = "Processing...") -> Activity:
        """Log thinking/processing state."""
        self._status = "thinking"
        return self.log(ActivityType.THINKING, content=message)

    def get_recent(self, limit: int = 50) -> list[dict]:
        """Get recent activities as dicts."""
        with self._lock:
            activities = list(self._activities)[-limit:]
        return [a.to_dict() for a in activities]

    def get_status(self) -> dict:
        """Get current status."""
        return {
            "status": self._status,
            "current_task": self._current_task,
            "activity_count": len(self._activities)
        }

    def clear(self):
        """Clear all activities."""
        with self._lock:
            self._activities.clear()
        self._status = "idle"
        self._current_task = None


# Global instance
activity_log = ActivityLog()
