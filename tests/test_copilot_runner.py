"""Tests for bridge/copilot_runner.py."""

import os
from unittest.mock import MagicMock, patch

from bridge.copilot_runner import run_copilot_cli


class TestRunCopilotCli:
    def test_successful_run(self, tmp_path):
        mock_result = MagicMock()
        mock_result.stdout = b"Task completed successfully."
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result), \
             patch("bridge.copilot_runner.SESSION_DIR", str(tmp_path)), \
             patch("bridge.copilot_runner.COPILOT_WORK_DIR", str(tmp_path)):
            result = run_copilot_cli("test prompt")

        assert result["status"] == "done"
        assert "Task completed" in result["output"]

    def test_empty_stdout_falls_back_to_session_file(self, tmp_path):
        mock_result = MagicMock()
        mock_result.stdout = b""
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run, \
             patch("bridge.copilot_runner.SESSION_DIR", str(tmp_path)), \
             patch("bridge.copilot_runner.COPILOT_WORK_DIR", str(tmp_path)):
            # Pre-create session file that matches the generated session name
            import time
            session_name = f"bridge-{int(time.time())}"
            session_file = tmp_path / f"{session_name}.md"
            session_file.write_text("Session output here")
            result = run_copilot_cli("test", session_name=session_name)

        assert result["output"] == "Session output here"

    def test_timeout_returns_partial(self, tmp_path):
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("copilot", 10)), \
             patch("bridge.copilot_runner.SESSION_DIR", str(tmp_path)), \
             patch("bridge.copilot_runner.COPILOT_WORK_DIR", str(tmp_path)):
            result = run_copilot_cli("test", timeout=10)

        assert result["status"] == "failed"
        assert "Timed out" in result["output"]

    def test_copilot_not_found(self, tmp_path):
        with patch("subprocess.run", side_effect=FileNotFoundError()), \
             patch("bridge.copilot_runner.SESSION_DIR", str(tmp_path)), \
             patch("bridge.copilot_runner.COPILOT_WORK_DIR", str(tmp_path)):
            result = run_copilot_cli("test")

        assert result["status"] == "failed"
        assert "not found" in result["output"]

    def test_allow_all_flag(self, tmp_path):
        mock_result = MagicMock()
        mock_result.stdout = b"done"
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run, \
             patch("bridge.copilot_runner.SESSION_DIR", str(tmp_path)), \
             patch("bridge.copilot_runner.COPILOT_WORK_DIR", str(tmp_path)), \
             patch("bridge.copilot_runner.COPILOT_ALLOW_ALL", True):
            run_copilot_cli("test")

        cmd = mock_run.call_args[0][0]
        assert "--allow-all" in cmd

    def test_safe_mode_no_allow_all(self, tmp_path):
        mock_result = MagicMock()
        mock_result.stdout = b"done"
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run, \
             patch("bridge.copilot_runner.SESSION_DIR", str(tmp_path)), \
             patch("bridge.copilot_runner.COPILOT_WORK_DIR", str(tmp_path)), \
             patch("bridge.copilot_runner.COPILOT_ALLOW_ALL", False):
            run_copilot_cli("test")

        cmd = mock_run.call_args[0][0]
        assert "--allow-all" not in cmd
