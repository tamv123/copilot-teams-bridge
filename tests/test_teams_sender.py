"""Tests for bridge/teams_sender.py."""

import json
from unittest.mock import MagicMock, patch

from bridge.teams_sender import (
    _build_text_payload,
    _split_text,
    send_card,
    send_text,
)


class TestBuildTextPayload:
    def test_wraps_text_in_adaptive_card(self):
        payload = _build_text_payload("Hello world")
        assert payload["type"] == "message"
        content = json.loads(payload["attachments"][0]["content"])
        assert content["type"] == "AdaptiveCard"
        assert content["body"][0]["text"] == "Hello world"

    def test_content_is_json_string(self):
        payload = _build_text_payload("test")
        assert isinstance(payload["attachments"][0]["content"], str)


class TestSplitText:
    def test_short_text_not_split(self):
        chunks = _split_text("short", 100)
        assert len(chunks) == 1
        assert chunks[0] == "short"

    def test_splits_at_line_boundaries(self):
        text = "line1\nline2\nline3\nline4\n"
        chunks = _split_text(text, 12)
        assert len(chunks) >= 2
        assert "".join(chunks) == text

    def test_empty_text(self):
        chunks = _split_text("", 100)
        assert len(chunks) == 1


class TestSendText:
    def test_no_webhook_url(self):
        with patch("bridge.teams_sender.TEAMS_WEBHOOK_URL", ""):
            result = send_text("test")
        assert not result["success"]
        assert "not configured" in result["error"]

    def test_successful_send(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 202
        with patch("bridge.teams_sender.TEAMS_WEBHOOK_URL", "https://test.webhook"), \
             patch("requests.post", return_value=mock_resp):
            result = send_text("hello")
        assert result["success"]

    def test_http_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad Request"
        with patch("bridge.teams_sender.TEAMS_WEBHOOK_URL", "https://test.webhook"), \
             patch("requests.post", return_value=mock_resp):
            result = send_text("hello")
        assert not result["success"]
        assert "400" in result["error"]

    def test_long_text_chunked(self):
        long_text = "\n".join(["x" * 100] * 50)  # 5000+ chars with line breaks
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("bridge.teams_sender.TEAMS_WEBHOOK_URL", "https://test.webhook"), \
             patch("requests.post", return_value=mock_resp) as mock_post:
            result = send_text(long_text)
        assert result["success"]
        assert mock_post.call_count >= 2


class TestSendCard:
    def test_card_with_facts_and_actions(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("bridge.teams_sender.TEAMS_WEBHOOK_URL", "https://test.webhook"), \
             patch("requests.post", return_value=mock_resp) as mock_post:
            result = send_card(
                "Title",
                "Body text",
                facts={"Key": "Value"},
                actions=[{"title": "Open", "url": "https://example.com"}],
            )
        assert result["success"]
        payload = mock_post.call_args[1]["json"]
        content = json.loads(payload["attachments"][0]["content"])
        assert content["body"][0]["text"] == "Title"
        assert len(content["actions"]) == 1
        assert any(f["title"] == "Key" for f in content["body"][2]["facts"])
