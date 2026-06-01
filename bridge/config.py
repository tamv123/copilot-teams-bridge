"""Configuration — all settings from environment variables or .env file."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _expanduser(p: str) -> str:
    return os.path.expanduser(p)


# --- Teams ---
TEAMS_WEBHOOK_URL: str = os.getenv("TEAMS_WEBHOOK_URL", "")
TEAMS_COMMANDS_DIR: str = _expanduser(os.getenv("TEAMS_COMMANDS_DIR", ""))
ALLOWED_SENDERS: list[str] = [
    s.strip().lower()
    for s in os.getenv("ALLOWED_SENDERS", "").split(",")
    if s.strip()
]

# --- Copilot CLI ---
COPILOT_WORK_DIR: str = _expanduser(os.getenv("COPILOT_WORK_DIR", "."))
COPILOT_SYSTEM_PROMPT: str = os.getenv(
    "COPILOT_SYSTEM_PROMPT",
    "You are a helpful AI assistant. Process the following request fully.",
)
COPILOT_MODEL: str = os.getenv("COPILOT_MODEL", "claude-sonnet-4-20250514")
COPILOT_TIMEOUT: int = int(os.getenv("COPILOT_TIMEOUT", "1800"))
COPILOT_ALLOW_ALL: bool = os.getenv("COPILOT_ALLOW_ALL", "false").lower() in ("true", "1", "yes")
COPILOT_MAX_CONTINUES: int = int(os.getenv("COPILOT_MAX_CONTINUES", "30"))

# --- Polling intervals ---
TEAMS_POLL_INTERVAL: int = int(os.getenv("TEAMS_POLL_INTERVAL", "120"))
QUEUE_POLL_INTERVAL: int = int(os.getenv("QUEUE_POLL_INTERVAL", "60"))
HEARTBEAT_INTERVAL: int = int(os.getenv("HEARTBEAT_INTERVAL", "3600"))

# --- Paths ---
DATA_DIR: str = _expanduser(os.getenv("DATA_DIR", "~/.config/copilot-teams-bridge"))
QUEUE_FILE: str = os.path.join(DATA_DIR, "queue.json")
LOCK_FILE: str = os.path.join(DATA_DIR, "copilot.lock")
PROCESSED_DIR: str = os.path.join(TEAMS_COMMANDS_DIR, "processed") if TEAMS_COMMANDS_DIR else ""

# --- Logging ---
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# --- File age threshold (seconds) to avoid reading partially-synced files ---
FILE_MIN_AGE: int = int(os.getenv("FILE_MIN_AGE", "5"))
