# Power Automate Setup Guide

This guide walks through configuring the two Power Automate Workflows needed
for the Copilot Teams Bridge.

## Prerequisites

- A Microsoft Teams channel where you want the bridge to operate
- Power Automate access (included with most M365 licenses)
- OneDrive for Business (for the inbound message relay)

---

## Workflow 1: Outbound — Receive Webhook Posts → Channel

This lets the bridge **send messages to Teams** via HTTP POST.

### Steps

1. In your Teams channel, click **⋯** → **Workflows**
2. Search for **"Post to a channel when a webhook request is received"**
3. Select it and follow the prompts:
   - Name: `Copilot Bridge Inbound`
   - Team: your team
   - Channel: your channel
4. Click **Create flow**
5. Copy the generated webhook URL

### Configuration

Set the webhook URL in your `.env` file:

```
TEAMS_WEBHOOK_URL=https://your-org.webhook.office.com/...
```

### Important Notes

- Use the **channel** workflow, NOT "Send webhook alerts to a chat"
  (chat webhooks cause `"Call made for a thread which is not a ChatThread"` errors)
- The webhook URL contains a signature — treat it as a secret
- Rate limit: 4 requests/second, 28 KB max payload

---

## Workflow 2: Inbound — Channel Messages → OneDrive JSON Files

This lets the bridge **receive messages from Teams** by monitoring the channel.

### Steps

1. Open [Power Automate](https://make.powerautomate.com/)
2. Click **+ Create** → **Automated cloud flow**
3. Name: `Copilot Bridge — Channel Monitor`
4. Trigger: **"When a new channel message is added"**
   - Team: your team
   - Channel: your channel

### Add Actions

5. Add action: **Compose**
   - Inputs (Expression):
   ```json
   json(concat('{"from":"', triggerOutputs()?['body/from/user/displayName'], '","text":"', replace(triggerOutputs()?['body/body/content'], '"', '\"'), '","ts":"', triggerOutputs()?['body/createdDateTime'], '"}'))
   ```

6. Add action: **Create file** (OneDrive for Business)
   - Folder: `/CopilotCommands`
   - File name: `msg-@{utcNow('yyyyMMddHHmmss')}.json`
   - File content: Output from Compose step

7. Save and test

### OneDrive Sync

The message files appear in your OneDrive folder, which syncs to your local machine:

| Platform | Typical Path |
|----------|-------------|
| Windows  | `C:\Users\you\OneDrive - Your Org\CopilotCommands` |
| WSL2     | `/mnt/c/Users/you/OneDrive - Your Org/CopilotCommands` |
| macOS    | `~/Library/CloudStorage/OneDrive-YourOrg/CopilotCommands` |

Set this in your `.env`:

```
TEAMS_COMMANDS_DIR=/mnt/c/Users/you/OneDrive - Your Org/CopilotCommands
```

### Message File Format

Each file looks like:

```json
{"from": "Doe, Jane", "text": "<p>check deployment status</p>", "ts": "2026-06-01T10:30:00Z"}
```

The bridge strips HTML tags and processes the plain text command.

---

## Testing

1. Post a message in the Teams channel: `ping`
2. Check that a `msg-*.json` file appears in the OneDrive folder
3. Run `copilot-teams-doctor` to verify connectivity
4. Start the bridge: `copilot-teams-bridge`
5. Post another message — you should see a reply in the channel

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No msg files appearing | Check Power Automate flow run history for errors |
| Files appear but bridge ignores them | Check `TEAMS_COMMANDS_DIR` path and file permissions |
| Webhook returns HTTP 400 | Verify payload format — `content` must be a JSON **string** |
| "ChatThread" error | Use channel workflow, not chat workflow |
| Messages not syncing | Check OneDrive sync status (system tray icon) |
| Duplicate processing | Files should be archived to `processed/` — check folder permissions |
