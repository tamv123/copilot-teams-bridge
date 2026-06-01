"""Asyncio daemon — polls Teams, processes queue, sends heartbeat.

Three concurrent loops:
  1. teams_loop:     Poll OneDrive folder for new Teams messages → enqueue
  2. queue_loop:     Process pending tasks via Copilot CLI → reply on Teams
  3. heartbeat_loop: Send periodic status message to Teams
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import time
from datetime import datetime

from bridge import config
from bridge.teams_sender import send_text

logger = logging.getLogger(__name__)

# --- Globals ---
shutdown_event = asyncio.Event()
loop_health: dict[str, dict] = {}


# --- Health tracking ---

def _init_health(name: str):
    loop_health[name] = {
        "last_success": None,
        "last_failure": None,
        "last_error": None,
        "consecutive_failures": 0,
        "total_runs": 0,
        "total_processed": 0,
    }


def _record_success(name: str, processed: int = 0):
    h = loop_health[name]
    h["last_success"] = datetime.now().isoformat()
    h["consecutive_failures"] = 0
    h["total_runs"] += 1
    h["total_processed"] += processed


def _record_failure(name: str, error: str):
    h = loop_health[name]
    h["last_failure"] = datetime.now().isoformat()
    h["last_error"] = error[:200]
    h["consecutive_failures"] += 1
    h["total_runs"] += 1


# --- Interruptible sleep ---

async def _interruptible_sleep(seconds: float):
    """Sleep that wakes early if shutdown is signalled."""
    try:
        await asyncio.wait_for(shutdown_event.wait(), timeout=seconds)
    except asyncio.TimeoutError:
        pass


# --- Signal handling ---

def _handle_signal(sig, _frame):
    logger.info("Received signal %s — shutting down", signal.Signals(sig).name)
    shutdown_event.set()


# --- Sync workers (run in thread pool) ---

def _teams_poll_sync() -> int:
    """Poll for Teams messages and enqueue them. Runs in thread."""
    from bridge.teams_poller import check_for_messages
    from bridge.queue import enqueue

    messages = check_for_messages()
    if not messages:
        return 0

    for msg in messages:
        text = msg["text"].strip()
        sender = msg["from"]
        lower = text.lower()

        # Handle simple built-in commands
        if lower in ("status", "status?", "ping"):
            send_text(f"✅ **Bridge is online** — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            continue
        if lower in ("test", "hello", "hi"):
            send_text(f"👋 Hey {sender.split(',')[0].strip()}! I'm here.")
            continue

        # Queue for Copilot CLI processing
        task_id = enqueue(text, sender)
        send_text(
            f"📝 Queued request #{task_id}.\n\n"
            f"*\"{text[:100]}{'…' if len(text) > 100 else ''}\"*\n\n"
            f"Processing within {config.QUEUE_POLL_INTERVAL}s."
        )

    return len(messages)


def _queue_process_sync() -> int:
    """Process pending queue items via Copilot CLI. Runs in thread."""
    from bridge.queue import acquire_copilot_lock, complete_task, get_pending, release_copilot_lock
    from bridge.copilot_runner import run_copilot_cli

    pending = get_pending()
    if not pending:
        return 0

    fd = acquire_copilot_lock()
    if fd is None:
        logger.info("Copilot lock busy — will retry next cycle")
        return 0

    processed = 0
    try:
        for task in pending:
            task_id = task["id"]
            text = task["text"]

            logger.info("Processing task #%d: %s", task_id, text[:80])
            send_text(f"⚙️ Processing #{task_id}: *{text[:100]}*")

            result = run_copilot_cli(text)
            output = result.get("output", "(no output)")
            status = result.get("status", "failed")

            complete_task(task_id, output, status)

            emoji = "✅" if status == "done" else "⚠️"
            send_text(
                f"{emoji} **#{task_id} — {status}**\n\n"
                f"{output[:2000]}"
            )
            processed += 1
    finally:
        release_copilot_lock(fd)

    return processed


def _heartbeat_sync():
    """Send a heartbeat status message to Teams. Runs in thread."""
    import resource

    mem_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [f"💓 **Bridge Heartbeat** — {now}\n"]
    for name, h in loop_health.items():
        status = "✅" if h["consecutive_failures"] == 0 else f"⚠️ ({h['consecutive_failures']} failures)"
        lines.append(f"- **{name}**: {status} | runs: {h['total_runs']} | processed: {h['total_processed']}")

    lines.append(f"\nMemory: {mem_mb:.0f} MB")
    send_text("\n".join(lines))


# --- Async loops ---

async def teams_loop():
    """Poll Teams messages on a fixed interval."""
    _init_health("teams")
    await _interruptible_sleep(5)  # Initial delay

    while not shutdown_event.is_set():
        try:
            count = await asyncio.to_thread(_teams_poll_sync)
            _record_success("teams", count)
            if count:
                logger.info("Teams: processed %d message(s)", count)
        except Exception as exc:
            _record_failure("teams", str(exc))
            logger.error("Teams loop error: %s", exc, exc_info=True)

        await _interruptible_sleep(config.TEAMS_POLL_INTERVAL)


async def queue_loop():
    """Process pending queue items on a fixed interval."""
    _init_health("queue")
    await _interruptible_sleep(15)  # Staggered start

    while not shutdown_event.is_set():
        try:
            count = await asyncio.to_thread(_queue_process_sync)
            _record_success("queue", count)
            if count:
                logger.info("Queue: processed %d task(s)", count)
        except Exception as exc:
            _record_failure("queue", str(exc))
            logger.error("Queue loop error: %s", exc, exc_info=True)

        await _interruptible_sleep(config.QUEUE_POLL_INTERVAL)


async def heartbeat_loop():
    """Send periodic heartbeat to Teams."""
    _init_health("heartbeat")
    await _interruptible_sleep(60)  # Wait 1 min before first heartbeat

    while not shutdown_event.is_set():
        try:
            await asyncio.to_thread(_heartbeat_sync)
            _record_success("heartbeat")
        except Exception as exc:
            _record_failure("heartbeat", str(exc))
            logger.error("Heartbeat error: %s", exc, exc_info=True)

        await _interruptible_sleep(config.HEARTBEAT_INTERVAL)


# --- Main ---

async def _run():
    """Launch all loops concurrently."""
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    os.makedirs(config.DATA_DIR, exist_ok=True)

    logger.info("=== Copilot Teams Bridge starting ===")
    logger.info("Teams folder: %s", config.TEAMS_COMMANDS_DIR or "(not set)")
    logger.info("Webhook: %s", "configured" if config.TEAMS_WEBHOOK_URL else "NOT SET")
    logger.info("Copilot allow-all: %s", config.COPILOT_ALLOW_ALL)
    logger.info("Allowed senders: %s", config.ALLOWED_SENDERS or "(all)")

    if not config.TEAMS_WEBHOOK_URL:
        logger.error("TEAMS_WEBHOOK_URL is required. Set it in .env or environment.")
        sys.exit(1)

    tasks = [
        asyncio.create_task(teams_loop()),
        asyncio.create_task(queue_loop()),
        asyncio.create_task(heartbeat_loop()),
    ]

    # Send startup notification
    try:
        send_text(f"🟢 **Copilot Teams Bridge started** — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    except Exception:
        pass

    await asyncio.gather(*tasks)
    logger.info("=== Copilot Teams Bridge stopped ===")


def main():
    """Entry point."""
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(_run())


if __name__ == "__main__":
    main()
