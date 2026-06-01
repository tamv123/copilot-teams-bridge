"""Tests for bridge/teams_poller.py."""

import json
import os
import time

from unittest.mock import patch

from bridge.teams_poller import (
    _is_sender_allowed,
    check_for_messages,
    read_message_file,
    strip_html,
)


class TestStripHtml:
    def test_strips_tags(self):
        assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_plain_text_unchanged(self):
        assert strip_html("no tags here") == "no tags here"

    def test_empty_string(self):
        assert strip_html("") == ""


class TestReadMessageFile:
    def test_valid_json(self, tmp_path):
        f = tmp_path / "msg-001.json"
        f.write_text(json.dumps({
            "from": "Doe, Jane",
            "text": "<p>check status</p>",
            "ts": "2026-06-01T10:00:00Z",
        }))
        msg = read_message_file(str(f))
        assert msg["from"] == "Doe, Jane"
        assert msg["text"] == "check status"
        assert msg["ts"] == "2026-06-01T10:00:00Z"

    def test_malformed_json_fallback(self, tmp_path):
        f = tmp_path / "msg-002.json"
        f.write_text('{"from": "Smith, Bob", "text": "hello <world>", "ts": "2026-01-01"}')
        msg = read_message_file(str(f))
        assert msg is not None
        assert msg["from"] == "Smith, Bob"

    def test_missing_file_returns_none(self):
        assert read_message_file("/nonexistent/msg-999.json") is None


class TestIsSenderAllowed:
    def test_empty_allowlist_allows_all(self):
        with patch("bridge.teams_poller.ALLOWED_SENDERS", []):
            assert _is_sender_allowed("Anyone, Really")

    def test_matching_sender_allowed(self):
        with patch("bridge.teams_poller.ALLOWED_SENDERS", ["doe, jane"]):
            assert _is_sender_allowed("Doe, Jane")

    def test_non_matching_sender_blocked(self):
        with patch("bridge.teams_poller.ALLOWED_SENDERS", ["doe, jane"]):
            assert not _is_sender_allowed("Smith, Bob")

    def test_case_insensitive(self):
        with patch("bridge.teams_poller.ALLOWED_SENDERS", ["doe"]):
            assert _is_sender_allowed("DOE, Jane")


class TestCheckForMessages:
    def test_returns_empty_when_dir_missing(self):
        with patch("bridge.teams_poller.TEAMS_COMMANDS_DIR", "/nonexistent"):
            assert check_for_messages() == []

    def test_skips_workflow_bot(self, tmp_path):
        cmd_dir = tmp_path / "cmds"
        cmd_dir.mkdir()
        proc_dir = cmd_dir / "processed"
        proc_dir.mkdir()

        f = cmd_dir / "msg-001.json"
        f.write_text(json.dumps({
            "from": "Workflows",
            "text": "bot message",
            "ts": "2026-01-01",
        }))
        # Touch file to make it old enough
        old_time = time.time() - 60
        os.utime(str(f), (old_time, old_time))

        with patch("bridge.teams_poller.TEAMS_COMMANDS_DIR", str(cmd_dir)), \
             patch("bridge.teams_poller.PROCESSED_DIR", str(proc_dir)), \
             patch("bridge.teams_poller.FILE_MIN_AGE", 5):
            msgs = check_for_messages()
        assert len(msgs) == 0

    def test_processes_valid_message(self, tmp_path):
        cmd_dir = tmp_path / "cmds"
        cmd_dir.mkdir()
        proc_dir = cmd_dir / "processed"
        proc_dir.mkdir()

        f = cmd_dir / "msg-001.json"
        f.write_text(json.dumps({
            "from": "Doe, Jane",
            "text": "deploy now",
            "ts": "2026-01-01",
        }))
        old_time = time.time() - 60
        os.utime(str(f), (old_time, old_time))

        with patch("bridge.teams_poller.TEAMS_COMMANDS_DIR", str(cmd_dir)), \
             patch("bridge.teams_poller.PROCESSED_DIR", str(proc_dir)), \
             patch("bridge.teams_poller.ALLOWED_SENDERS", []), \
             patch("bridge.teams_poller.FILE_MIN_AGE", 5):
            msgs = check_for_messages()
        assert len(msgs) == 1
        assert msgs[0]["text"] == "deploy now"

    def test_skips_young_files(self, tmp_path):
        cmd_dir = tmp_path / "cmds"
        cmd_dir.mkdir()
        proc_dir = cmd_dir / "processed"
        proc_dir.mkdir()

        f = cmd_dir / "msg-001.json"
        f.write_text(json.dumps({
            "from": "Doe, Jane",
            "text": "hello",
            "ts": "2026-01-01",
        }))
        # File is brand new — should be skipped

        with patch("bridge.teams_poller.TEAMS_COMMANDS_DIR", str(cmd_dir)), \
             patch("bridge.teams_poller.PROCESSED_DIR", str(proc_dir)), \
             patch("bridge.teams_poller.ALLOWED_SENDERS", []), \
             patch("bridge.teams_poller.FILE_MIN_AGE", 9999):
            msgs = check_for_messages()
        assert len(msgs) == 0
