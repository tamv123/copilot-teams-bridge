"""Poll for new Teams messages from OneDrive-synced folder.

Power Automate writes JSON files to a OneDrive folder when messages
arrive in the configured Teams channel. This module reads those files,
parses the messages, and archives them after processing.
"""

from __future__ import annotations

import glob
import json
import logging
import os
import re
import shutil
import time
from html.parser import HTMLParser

from bridge.config import (
    ALLOWED_SENDERS,
    FILE_MIN_AGE,
    PROCESSED_DIR,
    TEAMS_COMMANDS_DIR,
)

logger = logging.getLogger(__name__)


class _HTMLStripper(HTMLParser):
    """Strip HTML tags and return plain text."""

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str):
        self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts).strip()


def strip_html(html: str) -> str:
    """Remove HTML tags, return plain text."""
    s = _HTMLStripper()
    s.feed(html)
    return s.get_text()


def read_message_file(path: str) -> dict | None:
    """Read and parse a single message JSON file.

    Expected format (from Power Automate):
        {"from": "Doe, Jane", "text": "<p>hello</p>", "ts": "2026-06-01T10:00:00Z"}

    Returns:
        dict with keys: from, text (HTML-stripped), ts, file — or None on error.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Fallback: extract fields via regex (handles malformed PA output)
            from_match = re.search(r'"from"\s*:\s*"([^"]*)"', raw)
            text_match = re.search(r'"text"\s*:\s*"(.*?)",\s*"ts"', raw, re.DOTALL)
            ts_match = re.search(r'"ts"\s*:\s*"([^"]*)"', raw)
            if not text_match:
                logger.warning("Cannot parse message file %s", path)
                return None
            data = {
                "from": from_match.group(1) if from_match else "Unknown",
                "text": text_match.group(1),
                "ts": ts_match.group(1) if ts_match else "",
            }

        return {
            "from": data.get("from", "Unknown"),
            "text": strip_html(data.get("text", "")),
            "ts": data.get("ts", ""),
            "file": path,
        }
    except (IOError, KeyError) as exc:
        logger.warning("Failed to read message file %s: %s", path, exc)
        return None


def _is_sender_allowed(sender: str) -> bool:
    """Check if the sender is in the allowed list.

    If ALLOWED_SENDERS is empty, all senders are allowed.
    """
    if not ALLOWED_SENDERS:
        return True
    sender_lower = sender.lower()
    return any(allowed in sender_lower for allowed in ALLOWED_SENDERS)


def archive_file(path: str):
    """Move a processed file to the processed/ subfolder."""
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    dest = os.path.join(PROCESSED_DIR, os.path.basename(path))
    try:
        shutil.move(path, dest)
    except OSError as exc:
        logger.warning("Failed to archive %s: %s", path, exc)


def check_for_messages() -> list[dict]:
    """Scan for new Teams message files and return parsed messages.

    Files are archived after reading. Messages from disallowed senders
    or bot accounts (e.g. "Workflows") are silently dropped.

    Returns:
        List of parsed message dicts with keys: from, text, ts, file.
    """
    if not TEAMS_COMMANDS_DIR or not os.path.isdir(TEAMS_COMMANDS_DIR):
        return []

    files = sorted(glob.glob(os.path.join(TEAMS_COMMANDS_DIR, "msg-*.json")))
    if not files:
        return []

    now = time.time()
    messages = []

    for f in files:
        # Skip files still being synced (younger than FILE_MIN_AGE seconds)
        try:
            file_age = now - os.path.getmtime(f)
            if file_age < FILE_MIN_AGE:
                logger.debug("Skipping %s (%.1fs old, min %ds)", f, file_age, FILE_MIN_AGE)
                continue
        except OSError:
            continue

        msg = read_message_file(f)
        if not msg or not msg["text"]:
            archive_file(f)
            continue

        # Skip bot messages (our own webhook posts)
        if "workflow" in msg["from"].lower():
            archive_file(f)
            continue

        # Sender authorization
        if not _is_sender_allowed(msg["from"]):
            logger.warning("Blocked message from unauthorized sender: %s", msg["from"])
            archive_file(f)
            continue

        messages.append(msg)
        archive_file(f)

    return messages
