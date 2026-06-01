"""JSON file-based task queue with atomic writes and file locking.

Tasks flow through: pending → processing → completed | failed.
Queue is persisted to a JSON file with atomic write (temp + rename).
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import tempfile
import time
from datetime import datetime
from typing import Any

from bridge.config import DATA_DIR, LOCK_FILE, QUEUE_FILE

logger = logging.getLogger(__name__)


def _atomic_write(path: str, data: Any):
    """Write JSON data atomically via temp file + rename."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=os.path.dirname(path), suffix=".tmp", prefix=".queue-"
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, default=str)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def load_queue() -> list[dict]:
    """Load the task queue from disk."""
    if os.path.exists(QUEUE_FILE):
        try:
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def save_queue(queue: list[dict]):
    """Persist the task queue atomically."""
    _atomic_write(QUEUE_FILE, queue)


def enqueue(text: str, sender: str = "teams") -> int:
    """Add a task to the pending queue.

    Args:
        text: The command/request text.
        sender: Who sent the request.

    Returns:
        The assigned task ID.
    """
    queue = load_queue()
    task_id = max((t["id"] for t in queue), default=0) + 1
    task = {
        "id": task_id,
        "text": text,
        "sender": sender,
        "status": "pending",
        "queued_at": datetime.now().isoformat(),
        "completed_at": None,
        "result": None,
    }
    queue.append(task)
    save_queue(queue)
    logger.info("Queued task #%d from %s: %s", task_id, sender, text[:80])
    return task_id


def get_pending() -> list[dict]:
    """Get all pending tasks."""
    return [t for t in load_queue() if t["status"] == "pending"]


def complete_task(task_id: int, result: str, status: str = "completed"):
    """Mark a task as completed (or failed) with result text."""
    queue = load_queue()
    for task in queue:
        if task["id"] == task_id:
            task["status"] = status
            task["completed_at"] = datetime.now().isoformat()
            task["result"] = result[:5000]
            break
    save_queue(queue)


# --- Cross-process file lock ---

def acquire_copilot_lock() -> int | None:
    """Acquire an exclusive non-blocking file lock for Copilot CLI execution.

    Returns:
        File descriptor on success, None if lock is held by another process.
    """
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
    try:
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except (OSError, BlockingIOError):
        return None


def release_copilot_lock(fd: int):
    """Release the Copilot CLI file lock."""
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    except OSError:
        pass
