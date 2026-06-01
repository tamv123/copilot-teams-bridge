# Copilot Teams Bridge

> Bridge Microsoft Teams ↔ GitHub Copilot CLI via Power Automate + asyncio daemon

**Send messages in a Teams channel → get AI-powered responses from Copilot CLI.**

No Microsoft Graph API, no app registration, no admin approval needed.
Uses Power Automate Workflows (included with M365) as the Teams interface.

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

## How It Works

1. You post a message in your Teams channel
2. Power Automate writes a JSON file to your OneDrive `/CopilotCommands/` folder
3. OneDrive syncs the file to your local machine
4. The daemon polls the folder every 2 minutes, reads new messages
5. Messages are queued and processed through Copilot CLI
6. Results are posted back to Teams via the webhook

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
