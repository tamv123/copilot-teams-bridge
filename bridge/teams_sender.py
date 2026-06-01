"""Send messages to Microsoft Teams via Power Automate Workflows webhook.

Supports plain text and Adaptive Cards. The webhook URL must be configured
via the TEAMS_WEBHOOK_URL environment variable.
"""

from __future__ import annotations

import json
import logging
import os

import requests

from bridge.config import TEAMS_WEBHOOK_URL

logger = logging.getLogger(__name__)

# Maximum payload size for Teams webhooks (~28 KB)
MAX_PAYLOAD_BYTES = 28_000
# Maximum text per message before splitting
MAX_TEXT_LENGTH = 3500


def send_text(text: str, webhook_url: str | None = None) -> dict:
    """Send a plain text message to Teams as an Adaptive Card.

    Args:
        text: Message text (markdown supported).
        webhook_url: Override webhook URL (defaults to config).

    Returns:
        dict with 'success' (bool) and 'error' (str | None).
    """
    url = webhook_url or TEAMS_WEBHOOK_URL
    if not url:
        return {"success": False, "error": "TEAMS_WEBHOOK_URL not configured"}

    # Split long messages
    if len(text) > MAX_TEXT_LENGTH:
        return _send_chunked(text, url)

    payload = _build_text_payload(text)
    return _post_webhook(url, payload)


def send_card(
    title: str,
    body_text: str,
    facts: dict | None = None,
    actions: list[dict] | None = None,
    webhook_url: str | None = None,
) -> dict:
    """Send a rich Adaptive Card to Teams.

    Args:
        title: Card title (bold, large).
        body_text: Main body text (markdown).
        facts: Optional dict of label→value pairs shown as a FactSet.
        actions: Optional list of {"title": str, "url": str} action buttons.
        webhook_url: Override webhook URL.

    Returns:
        dict with 'success' and 'error'.
    """
    url = webhook_url or TEAMS_WEBHOOK_URL
    if not url:
        return {"success": False, "error": "TEAMS_WEBHOOK_URL not configured"}

    card_body = [
        {"type": "TextBlock", "text": title, "weight": "Bolder", "size": "Medium"},
        {"type": "TextBlock", "text": body_text, "wrap": True},
    ]

    if facts:
        card_body.append({
            "type": "FactSet",
            "facts": [{"title": k, "value": str(v)} for k, v in facts.items()],
        })

    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": card_body,
    }

    if actions:
        card["actions"] = [
            {"type": "Action.OpenUrl", "title": a["title"], "url": a["url"]}
            for a in actions
        ]

    payload = {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": json.dumps(card),
        }],
    }

    return _post_webhook(url, payload)


def _build_text_payload(text: str) -> dict:
    """Build an Adaptive Card payload wrapping plain text."""
    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": json.dumps({
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": [{"type": "TextBlock", "text": text, "wrap": True}],
            }),
        }],
    }


def _send_chunked(text: str, url: str) -> dict:
    """Split a long message into chunks and send each separately."""
    chunks = _split_text(text, MAX_TEXT_LENGTH)
    last_result = {"success": True, "error": None}

    for i, chunk in enumerate(chunks):
        header = f"*[Part {i + 1}/{len(chunks)}]*\n\n" if len(chunks) > 1 else ""
        payload = _build_text_payload(header + chunk)
        result = _post_webhook(url, payload)
        if not result["success"]:
            return result
        last_result = result

    return last_result


def _split_text(text: str, max_len: int) -> list[str]:
    """Split text into chunks at line boundaries."""
    lines = text.splitlines(keepends=True)
    chunks: list[str] = []
    current = ""

    for line in lines:
        if len(current) + len(line) > max_len and current:
            chunks.append(current)
            current = ""
        current += line

    if current:
        chunks.append(current)

    return chunks or [text]


def _post_webhook(url: str, payload: dict) -> dict:
    """POST a payload to the Teams webhook URL."""
    try:
        # Support custom CA bundles for corporate proxies
        ca_bundle = os.environ.get("SSL_CERT_FILE", "")
        verify: str | bool = ca_bundle if ca_bundle and os.path.exists(ca_bundle) else True

        resp = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15,
            verify=verify,
        )

        if resp.status_code in (200, 202):
            logger.info("Teams message sent successfully")
            return {"success": True, "error": None}

        error = f"HTTP {resp.status_code}: {resp.text[:200]}"
        logger.error("Teams webhook failed: %s", error)
        return {"success": False, "error": error}

    except requests.exceptions.RequestException as exc:
        error = str(exc)[:200]
        logger.error("Teams webhook request failed: %s", error)
        return {"success": False, "error": error}
