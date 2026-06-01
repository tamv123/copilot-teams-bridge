# Architecture

## System Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                    Microsoft Teams Channel                    │
│                                                              │
│  User posts message                    Bridge posts reply    │
│       │                                       ▲              │
└───────┼───────────────────────────────────────┼──────────────┘
        │                                       │
        ▼                                       │
┌───────────────────┐               ┌───────────────────────┐
│  Power Automate   │               │   Power Automate      │
│  Workflow #2      │               │   Workflow #1         │
│  (Channel Monitor)│               │   (Webhook Receiver)  │
│                   │               │                       │
│  Trigger: new msg │               │  Receives HTTP POST   │
│  Action: write    │               │  Posts to channel     │
│  JSON to OneDrive │               │                       │
└────────┬──────────┘               └───────────▲───────────┘
         │                                      │
         ▼                                      │
┌────────────────────┐              ┌───────────┴───────────┐
│  OneDrive Sync     │              │  teams_sender.py      │
│                    │              │                       │
│  /CopilotCommands/ │              │  send_text()          │
│  msg-{ts}.json     │              │  send_card()          │
│       │            │              │  POST → webhook URL   │
└───────┼────────────┘              └───────────▲───────────┘
        │                                       │
        ▼                                       │
┌────────────────────────────────────────────────┴──────────┐
│                    Asyncio Daemon (daemon.py)              │
│                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │  teams_loop   │  │  queue_loop   │  │ heartbeat_loop │  │
│  │  (120s poll)  │  │  (60s poll)   │  │ (3600s)        │  │
│  │              │  │              │  │                │  │
│  │  Read JSON   │  │  Get pending │  │  Send status   │  │
│  │  files →     │  │  tasks →     │  │  to Teams      │  │
│  │  enqueue     │  │  run CLI →   │  │                │  │
│  │              │  │  reply       │  │                │  │
│  └──────┬───────┘  └──────┬───────┘  └────────────────┘  │
│         │                 │                               │
│         ▼                 ▼                               │
│  ┌──────────────┐  ┌──────────────┐                      │
│  │  queue.py     │  │copilot_      │                      │
│  │              │  │runner.py     │                      │
│  │  JSON file   │  │              │                      │
│  │  task queue   │  │  subprocess  │                      │
│  │  + file lock  │  │  copilot CLI │                      │
│  └──────────────┘  └──────────────┘                      │
└──────────────────────────────────────────────────────────┘
```

## Components

| Component | File | Purpose |
|-----------|------|---------|
| **Daemon** | `bridge/daemon.py` | Asyncio event loop with 3 concurrent tasks |
| **Teams Sender** | `bridge/teams_sender.py` | Send messages/cards to Teams via webhook |
| **Teams Poller** | `bridge/teams_poller.py` | Read message files from OneDrive folder |
| **Copilot Runner** | `bridge/copilot_runner.py` | Execute Copilot CLI as subprocess |
| **Queue** | `bridge/queue.py` | JSON file-based task queue with file locking |
| **Config** | `bridge/config.py` | Environment-based configuration |
| **Doctor** | `bridge/doctor.py` | Setup diagnostics and connectivity checks |

## Message Lifecycle

1. **User posts** in Teams channel
2. **Power Automate** writes `msg-{ts}.json` to OneDrive
3. **OneDrive syncs** file to local disk
4. **teams_loop** reads file, strips HTML, checks sender authorization
5. Built-in commands (`ping`, `status`) → immediate reply
6. All other messages → **enqueue** as pending task
7. **queue_loop** picks up pending task, acquires file lock
8. **copilot_runner** executes `copilot -p "..." --autopilot`
9. Result sent back to Teams via **teams_sender** webhook
10. Task marked completed, file archived to `processed/`

## Security Model

- **Sender allowlist**: Only messages from `ALLOWED_SENDERS` are processed
- **Safe mode default**: `COPILOT_ALLOW_ALL=false` — Copilot runs without `--allow-all`
- **File lock**: Prevents concurrent Copilot CLI execution
- **No credentials in code**: Webhook URL and all secrets via env vars only
- **Message age check**: Files younger than 5s are skipped (sync race prevention)

## Fault Isolation

Each loop runs independently. If the Teams poller crashes, the queue processor
and heartbeat continue running. Per-loop health metrics track:

- `consecutive_failures`: resets on success
- `total_runs` / `total_processed`: cumulative counters
- `last_error`: truncated error message

The heartbeat reports all loop health to Teams every hour.
