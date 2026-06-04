## 🚀 Work in Progress

This repository is a work in progress, and I am actively looking for feedback and contributors to help refine it! 

If you see something that can be optimized, a bug that needs squashing, or want to co-develop a feature, please feel free to:
1. Open an **Issue** to discuss your ideas.
2. Submit a **Pull Request** with your improvements.

Let's collaborate and make this tool awesome!

# Copilot Teams Bridge

[![Platform: Windows](https://img.shields.io/badge/platform-Windows%20%7C%20WSL2-blue?logo=windows)](https://github.com/tamv123/copilot-teams-bridge)
[![Platform: macOS](https://img.shields.io/badge/platform-macOS-blue?logo=apple)](https://github.com/tamv123/copilot-teams-bridge)
[![Platform: Linux](https://img.shields.io/badge/platform-Linux-blue?logo=linux&logoColor=white)](https://github.com/tamv123/copilot-teams-bridge)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-brightgreen?logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Tests: 37 passed](https://img.shields.io/badge/tests-37%20passed-brightgreen)](tests/)

> Bridge Microsoft Teams ↔ GitHub Copilot CLI via Power Automate + asyncio daemon

**Send a message in Teams → get an AI-powered answer back — right in the same channel.**

No Microsoft Graph API, no app registration, no admin approval needed.
Uses Power Automate Workflows (included with M365) as the Teams interface.

## Why?

GitHub Copilot CLI is powerful, but it lives in your terminal. What if you could
talk to it from **Microsoft Teams** — the app you already have open all day?

With this bridge, you type a message in a Teams channel, and Copilot CLI processes
it on your machine. The result appears as a reply in the same channel within minutes.

**Use cases:**

- 🔍 *"What changed in the last 3 commits?"* — Copilot checks git log and summarizes
- 🐛 *"Why is the login test failing?"* — Copilot reads test output, finds the bug
- 📊 *"Summarize the open issues in our repo"* — Copilot queries GitHub and reports back
- 🚀 *"Deploy the staging branch"* — Copilot runs your deploy script (with `COPILOT_ALLOW_ALL=true`)
- 📝 *"Draft a PR description for the auth refactor"* — Copilot reads the diff and writes it

All from your phone, tablet, or any device with Teams — no terminal needed.

## What It Looks Like

```
┌─────────────────────────────────────────────────────┐
│  #copilot-bridge channel                            │
│                                                     │
│  👤 You:                                            │
│  What are the top 5 largest files in the repo?      │
│                                                     │
│  🤖 Copilot Bridge:                                 │
│  📝 Queued request #7.                              │
│  "What are the top 5 largest files in the repo?"    │
│  Processing within 60s.                             │
│                                                     │
│  🤖 Copilot Bridge:                                 │
│  ⚙️ Processing #7: What are the top 5 largest...    │
│                                                     │
│  🤖 Copilot Bridge:                                 │
│  ✅ #7 — done                                       │
│                                                     │
│  Here are the top 5 largest files:                  │
│  1. data/model.bin — 48 MB                          │
│  2. assets/video.mp4 — 22 MB                        │
│  3. vendor/lib.wasm — 15 MB                         │
│  4. docs/architecture.pdf — 8 MB                    │
│  5. test/fixtures/dump.sql — 6 MB                   │
└─────────────────────────────────────────────────────┘
```

Every request goes through 3 stages:
1. **📝 Queued** — acknowledged immediately with a task ID
2. **⚙️ Processing** — Copilot CLI is working on it
3. **✅ Done** (or ⚠️ Failed) — result posted back with full output

The bridge also sends a **💓 heartbeat** every hour so you know it's alive.

## How It Works (under the hood)

```
Teams Channel  ──→  Power Automate  ──→  OneDrive JSON  ──→  Daemon  ──→  Copilot CLI
     ↑                                                                         │
     └──────────────────  Webhook  ←──  teams_sender  ←──  Result  ←───────────┘
```

## Quick Start

### 1. Install

```bash
git clone https://github.com/tamv123/copilot-teams-bridge.git
cd copilot-teams-bridge
pip install -e .
```

### 2. Prerequisites

- **Python 3.10+**
- **GitHub Copilot CLI** installed and authenticated (`gh auth login`)
- **Microsoft Teams** channel with Power Automate Workflows
- **OneDrive for Business** syncing to local disk

### 3. Configure

```bash
cp .env.example .env
# Edit .env with your values
```

Required settings:

| Variable | Description |
|----------|-------------|
| `TEAMS_WEBHOOK_URL` | Power Automate webhook URL for posting to your channel |
| `TEAMS_COMMANDS_DIR` | Local path to OneDrive-synced commands folder |
| `ALLOWED_SENDERS` | Comma-separated sender names to authorize (security) |
| `COPILOT_WORK_DIR` | Working directory for Copilot CLI execution |

### 4. Set Up Power Automate

Follow [docs/power-automate-setup.md](docs/power-automate-setup.md) to create:

1. **Outbound workflow**: Webhook → Teams channel (for bridge → Teams messages)
2. **Inbound workflow**: Channel message → OneDrive JSON file (for Teams → bridge messages)

### 5. Verify Setup

```bash
copilot-teams-doctor
```

This checks: Python version, Copilot CLI, GitHub auth, webhook, OneDrive folder,
data directory, sender config, and webhook connectivity.

### 6. Run

```bash
# Foreground (for testing)
copilot-teams-bridge

# As a systemd user service (Linux/WSL)
cp bridge.service ~/.config/systemd/user/copilot-teams-bridge.service
systemctl --user daemon-reload
systemctl --user enable --now copilot-teams-bridge

# As a macOS LaunchAgent
cp bridge.plist ~/Library/LaunchAgents/com.copilot-teams-bridge.plist
# Edit the plist to set your WorkingDirectory, then:
launchctl load ~/Library/LaunchAgents/com.copilot-teams-bridge.plist
```

## How It Works (under the hood)

1. You post a message in your Teams channel (from any device)
2. Power Automate detects it and writes a JSON file to your OneDrive
3. OneDrive syncs the file to your local machine (Windows, Mac, or Linux)
4. The daemon picks it up within 2 minutes, queues it, and acknowledges on Teams
5. Copilot CLI processes the request in your project directory (with full repo context)
6. The result is posted back to the same Teams channel

**Response time:** ~2-5 minutes depending on complexity (polling + CLI execution).

### Built-in Commands

| Command | Response |
|---------|----------|
| `ping` / `status` | Bridge status check |
| `hello` / `hi` | Greeting |
| Anything else | Queued for Copilot CLI processing |

### Daemon Loops

| Loop | Interval | Purpose |
|------|----------|---------|
| `teams_loop` | 120s | Poll OneDrive for new message files |
| `queue_loop` | 60s | Process pending tasks via Copilot CLI |
| `heartbeat_loop` | 3600s | Send status heartbeat to Teams |

## Security

⚠️ **This bridge executes AI-generated commands on your machine.** Use with caution.

| Control | Default | Description |
|---------|---------|-------------|
| `ALLOWED_SENDERS` | empty (all) | Restrict who can send commands |
| `COPILOT_ALLOW_ALL` | `false` | Safe mode — Copilot cannot edit files or run commands without approval |
| File lock | enabled | Prevents concurrent Copilot CLI execution |
| File age check | 5s | Prevents reading partially-synced files |
| Webhook URL | env only | Never committed to code |

**Recommendation**: Always set `ALLOWED_SENDERS` and keep `COPILOT_ALLOW_ALL=false`
unless you understand the risks of full autopilot mode.

## Project Structure

```
copilot-teams-bridge/
├── bridge/
│   ├── daemon.py          # Asyncio daemon (3 loops)
│   ├── teams_sender.py    # Send messages/cards to Teams
│   ├── teams_poller.py    # Read message files from OneDrive
│   ├── copilot_runner.py  # Execute Copilot CLI subprocess
│   ├── queue.py           # JSON task queue + file locking
│   ├── config.py          # Env-based configuration
│   └── doctor.py          # Setup diagnostics
├── bridge.service         # Systemd unit template (Linux/WSL)
├── bridge.plist           # LaunchAgent plist (macOS)
├── examples/              # Sample message files
├── tests/                 # Test suite
└── docs/
    ├── power-automate-setup.md
    ├── architecture.md
    └── troubleshooting.md
```

## Testing

```bash
pip install -e ".[dev]"
pytest -v
```

## Docs

- [Architecture](docs/architecture.md) — system diagram and component details
- [Power Automate Setup](docs/power-automate-setup.md) — step-by-step workflow configuration
- [Troubleshooting](docs/troubleshooting.md) — common issues and diagnostic commands

## Origin

Extracted from [Victor's Assistant](https://github.com/tamv123/victors-assistant) —
a personal AI assistant system that bridges multiple channels (Teams, Email, WhatsApp,
SharePoint) to GitHub Copilot CLI via asyncio daemons.

## License

MIT
