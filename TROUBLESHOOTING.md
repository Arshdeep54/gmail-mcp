# Troubleshooting

## Setup Issues

### "credentials.json not found"

**Problem:** Running `python authorize.py` fails with this error.

**Solution:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project (or create one)
3. Enable the **Gmail API**: APIs & Services → Library → search "Gmail" → click Gmail API → Enable
4. Go to **APIs & Services → Credentials** → **Create Credentials** → **OAuth client ID**
5. Choose **Desktop app**
6. Download the JSON file and save it to `secrets/credentials.json` in your project root

If the credentials file is in a different location, set `GMAIL_MCP_CREDENTIALS` environment variable:
```bash
export GMAIL_MCP_CREDENTIALS=/path/to/your/credentials.json
python authorize.py
```

### "Access denied" during authorization

**Problem:** Google says your app is "untrusted" or you can't proceed past the permission screen.

**Solution:** If your project is in Testing mode, you need to add yourself as a test user:
1. In Google Cloud Console, go to **APIs & Services → OAuth consent screen**
2. Under **Test users**, click **Add users**
3. Add the Gmail address you're authorizing (e.g., your personal Gmail)
4. Try `python authorize.py` again

### "Port already in use" during authorization

**Problem:** `python authorize.py` fails with "Address already in use" or similar.

**Solution:** The authorization server is trying to use a local port that's taken. This usually resolves itself (the script picks a random port). If it persists:
```bash
# Find what's using port 8080 (or the displayed port)
lsof -i :8080
# Kill the process if it's not needed
kill -9 <PID>
# Try again
python authorize.py
```

### Token expired or invalid

**Problem:** "No valid credentials" error, or the server logs `google.auth.exceptions.RefreshError: invalid_grant: Token has been expired or revoked.`

**Cause:** If your Google Cloud OAuth consent screen is still in **Testing** mode, Google hard-expires refresh tokens after 7 days, no matter how often they're used. This is the most common cause and it will keep happening on a 7-day cycle until you publish the app.

**Immediate fix:** Re-authorize to get a working token again:
```bash
GMAIL_MCP_CREDENTIALS=secrets/credentials.json GMAIL_MCP_TOKEN=secrets/token.json python authorize.py
```
Then copy the new `secrets/token.json` to your server and restart the container (see [DEPLOYMENT.md](DEPLOYMENT.md#restarting)).

**Permanent fix — publish the app out of Testing:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/) → **APIs & Services → OAuth consent screen**
2. Click **Publish App**, then confirm
3. You'll see a warning that the app needs verification if it requests sensitive/restricted scopes to more than 100 users — this doesn't apply here: `gmail.readonly` and `gmail.compose` are sensitive scopes, but Google only requires the formal verification process (which can take weeks) once you have real external users beyond yourself. For single-tenant personal use, publishing is enough; you'll just see an "unverified app" warning on first consent, which is expected and safe to click through since it's your own app and your own data
4. Re-authorize once more after publishing: `python authorize.py`

Once published, refresh tokens don't expire on a fixed schedule — they only die if unused for 6 months, or if you revoke access yourself. See the cron keep-alive below if you want a safeguard against that.

## Docker / Deployment Issues

### "Connection refused" when connecting from ChatGPT

**Problem:** ChatGPT can't reach your server at `https://your-domain/mcp`.

**Solution:**
1. Verify your reverse proxy (Nginx/Caddy) is running and forwarding to port 8811
2. Check your domain DNS is pointing to your server's IP
3. Verify HTTPS is working: `curl -I https://your-domain/mcp` should show a 404 or the MCP endpoint
4. Check firewall rules allow 443 (HTTPS) inbound
5. Ensure the Docker container is running: `docker compose ps`

### "Connection refused" when connecting from Claude Code

**Problem:** Claude Code can't reach the server on localhost.

**Solution:**
1. Ensure the server is running: `python -m gmail_mcp.server` (local) or `docker compose up` (Docker)
2. Check your Claude Code MCP config has the correct path to the server
3. If using a custom Python path, verify it's in your `PATH`: `which python`

### Container won't start

**Problem:** `docker compose up` fails or container exits immediately.

**Solution:**
1. Check logs: `docker compose logs gmail-mcp`
2. Verify `.env` file exists and is valid
3. Ensure `secrets/credentials.json` exists
4. Check that `secrets/` directory is writable: `ls -la secrets/`
5. Rebuild the image: `docker compose down && docker compose up -d --build`

### "OAuth passphrase incorrect" on consent screen

**Problem:** You enter the passphrase but it's rejected.

**Solution:**
1. Check your `.env` file has the correct `GMAIL_MCP_OAUTH_PASSPHRASE` value
2. Restart the container: `docker compose restart gmail-mcp`
3. Generate a new passphrase if you forgot it:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(24))"
   ```
   Add it to `.env` and restart.

### "OAuth client ID mismatch"

**Problem:** ChatGPT says the client ID doesn't match.

**Solution:**
1. In your `.env`, find `GMAIL_MCP_OAUTH_CLIENT_ID` (the value you set, not a secret)
2. In ChatGPT's custom connector settings, paste this exact same client ID
3. Make sure you're using "OAuth" authentication, not "API key"
4. Restart the container after any `.env` changes

## MCP Client Issues

### Server doesn't appear in Claude Code

**Problem:** Added the MCP to Claude Code config but it doesn't show up.

**Solution:**
1. Verify your config path: `~/.claude/settings.json`
2. Check the config format:
   ```json
   {
     "mcpServers": {
       "gmail": {
         "command": "python",
         "args": ["-m", "gmail_mcp.server"],
         "cwd": "/full/path/to/gmail-mcp-server"
       }
     }
   }
   ```
3. Restart Claude Code after editing settings
4. Check Claude Code logs for errors: `cat ~/.claude/logs/claude-code.log` (varies by OS)

### "gmailSearchMessages: Invalid OAuth token"

**Problem:** The tool runs but fails with an OAuth error.

**Solution:**
1. Your token has expired (if using local stdio mode)
2. Re-run `python authorize.py`
3. Restart Claude Code

### Slow responses or timeouts

**Problem:** Queries take a long time or timeout.

**Solution:**
1. This is usually a network issue, not the server
2. Check your Gmail account actually has messages (empty inbox = instant responses)
3. Large searches may take a few seconds — Gmail's API is normally the bottleneck
4. If behind a slow VPN, the server may timeout waiting for Google's API

## Debug Mode

To see detailed logs of what the server is doing:

**Local:**
```bash
LOGLEVEL=debug python -m gmail_mcp.server
```

**Docker:**
```bash
docker compose exec gmail-mcp sh
# Inside the container:
LOGLEVEL=debug python -m gmail_mcp.server
```

This prints all API calls and token refresh events, useful for tracking down auth issues.

---

Still stuck? Check:
- Your `.env` file is in the project root
- `secrets/credentials.json` exists and is readable
- Your Google account is added as a test user (for Testing apps)
- Your reverse proxy (if deployed) is working

