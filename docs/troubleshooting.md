# Troubleshooting

## Common Issues

### Bridge starts but no messages are processed

1. **Check OneDrive sync**: Is the OneDrive client running and syncing?
   - Windows: Look for OneDrive icon in system tray
   - WSL: Check that `/mnt/c/Users/.../OneDrive - .../CopilotCommands/` is accessible

2. **Check file age**: Files younger than 5 seconds are skipped to prevent
   reading partially-synced files. If OneDrive is slow, increase `FILE_MIN_AGE`.

3. **Check sender allowlist**: If `ALLOWED_SENDERS` is set, verify the sender's
   display name matches. Run with `LOG_LEVEL=DEBUG` for details.

### Webhook returns HTTP 400 or 403

- The `content` field in Adaptive Card payloads must be a **JSON string**,
  not a nested JSON object
- The `contentUrl` field must be **omitted entirely** (not set to `null`)
- Verify the webhook URL hasn't expired — some Power Automate URLs rotate

### "ChatThread" error from Power Automate

Use the **channel** webhook workflow ("Post to a channel when a webhook
request is received"), NOT the chat variant ("Send webhook alerts to a chat").

### Copilot CLI not found

```
❌ Copilot CLI installed  (not found in PATH)
```

- Install: `gh extension install github/gh-copilot`
- Or install standalone: see [GitHub Copilot CLI docs](https://docs.github.com/en/copilot/using-github-copilot/using-github-copilot-in-the-command-line)
- If using systemd, ensure PATH includes the directory containing `copilot`

### Copilot CLI returns no output

- Check `gh auth status` — you need an active GitHub session
- Try running manually: `copilot -p "hello" --autopilot --silent`
- Check the session file in `~/.config/copilot-teams-bridge/sessions/`

### Queue tasks stuck in "pending"

- The file lock (`copilot.lock`) may be held by a crashed process
- Remove the lock: `rm ~/.config/copilot-teams-bridge/copilot.lock`
- Restart the bridge

### SSL certificate errors (corporate proxy)

Set `SSL_CERT_FILE` to your corporate CA bundle:

```bash
export SSL_CERT_FILE=/path/to/ca-bundle.crt
```

### Duplicate messages

- Check that the `processed/` subfolder exists and is writable
- If OneDrive re-syncs files, they may get re-processed. The bridge archives
  files to `processed/` to prevent this.

## Diagnostic Commands

```bash
# Run full diagnostics
copilot-teams-doctor

# Check daemon status (systemd)
systemctl --user status copilot-teams-bridge

# View logs
journalctl --user -u copilot-teams-bridge -f

# Test webhook manually
curl -X POST "$TEAMS_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{"type":"message","attachments":[{"contentType":"application/vnd.microsoft.card.adaptive","content":"{\"type\":\"AdaptiveCard\",\"version\":\"1.4\",\"body\":[{\"type\":\"TextBlock\",\"text\":\"Test message\",\"wrap\":true}]}"}]}'

# Check pending queue
python3 -c "from bridge.queue import get_pending; print(get_pending())"

# Check OneDrive folder
ls -la "$TEAMS_COMMANDS_DIR"/msg-*.json
```
