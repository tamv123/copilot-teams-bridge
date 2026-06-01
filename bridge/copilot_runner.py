"""Run requests through GitHub Copilot CLI as a subprocess.

Wraps the `copilot` command with configurable prompt, model, timeout,
and execution mode (safe by default, full autopilot opt-in).
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from typing import Any

from bridge.config import (
    COPILOT_ALLOW_ALL,
    COPILOT_MAX_CONTINUES,
    COPILOT_MODEL,
    COPILOT_SYSTEM_PROMPT,
    COPILOT_TIMEOUT,
    COPILOT_WORK_DIR,
    DATA_DIR,
)

logger = logging.getLogger(__name__)

SESSION_DIR = os.path.join(DATA_DIR, "sessions")


def run_copilot_cli(
    prompt: str,
    timeout: int | None = None,
    model: str | None = None,
    session_name: str | None = None,
) -> dict[str, Any]:
    """Run a request through Copilot CLI in non-interactive mode.

    Args:
        prompt: The user's request text.
        timeout: Execution timeout in seconds (default from config).
        model: LLM model to use (default from config).
        session_name: Named session for resume support.

    Returns:
        dict with keys:
            status: "done" | "failed"
            output: CLI output text
            session_name: session identifier
    """
    timeout = timeout or COPILOT_TIMEOUT
    model = model or COPILOT_MODEL
    session_name = session_name or f"bridge-{int(time.time())}"

    full_prompt = (
        f"{COPILOT_SYSTEM_PROMPT}\n\n"
        f"Request:\n{prompt}"
    )

    os.makedirs(SESSION_DIR, exist_ok=True)
    session_file = os.path.join(SESSION_DIR, f"{session_name}.md")

    cmd = [
        "copilot",
        "-p", full_prompt,
        "--autopilot",
        "--no-ask-user",
        "--max-autopilot-continues", str(COPILOT_MAX_CONTINUES),
        "--silent",
        "--no-color",
        "--model", model,
        f"--share={session_file}",
        "-n", session_name,
    ]

    if COPILOT_ALLOW_ALL:
        cmd.append("--allow-all")

    logger.info(
        "Running Copilot CLI [%s] session=%s: %s",
        model, session_name, prompt[:100],
    )

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            cwd=os.path.expanduser(COPILOT_WORK_DIR),
        )
        stdout = result.stdout.decode("utf-8", errors="replace").strip()

        output = stdout
        if not output and os.path.exists(session_file):
            with open(session_file, "r", encoding="utf-8") as f:
                output = f.read().strip()

        if not output:
            logger.warning(
                "Copilot CLI returned no output (exit=%d)", result.returncode
            )
            return {
                "status": "failed",
                "output": "(no output from Copilot CLI)",
                "session_name": session_name,
            }

        return {
            "status": "done",
            "output": output,
            "session_name": session_name,
        }

    except subprocess.TimeoutExpired:
        logger.warning("Copilot CLI timed out after %ds", timeout)
        partial = ""
        if os.path.exists(session_file):
            try:
                with open(session_file, "r") as f:
                    partial = f.read().strip()
            except Exception:
                pass
        return {
            "status": "failed",
            "output": (
                partial
                + f"\n\n[Timed out after {timeout}s. Partial result above.]"
            ),
            "session_name": session_name,
        }

    except FileNotFoundError:
        logger.error("Copilot CLI not found in PATH — is it installed?")
        return {
            "status": "failed",
            "output": "Error: `copilot` command not found. Install GitHub Copilot CLI first.",
            "session_name": session_name,
        }

    except Exception as exc:
        logger.error("Copilot CLI error: %s", exc)
        return {
            "status": "failed",
            "output": f"Error: {exc}",
            "session_name": session_name,
        }
