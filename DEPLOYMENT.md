# Deployment Guide

This guide covers deploying gmail-mcp-server to a hosted environment (EC2, DigitalOcean, Linode, etc.) so ChatGPT and other MCP clients can connect over HTTPS.

## Prerequisites

- A Linux server (Ubuntu 20.04+ or equivalent)
- A domain name pointing to your server
- Docker and Docker Compose installed
- A reverse proxy (Caddy, Nginx, or similar) to handle HTTPS

## Step 1: Set Up Your Domain and Reverse Proxy

### Option A: Caddy (Recommended — simplest)

Install Caddy:
```bash
sudo apt-get update
sudo apt-get install -y caddy
```

Create a Caddyfile at `/etc/caddy/Caddyfile`:
```caddy
gmail-mcp.example.com {
    reverse_proxy localhost:8811
}
```

Replace `gmail-mcp.example.com` with your actual domain. Caddy automatically handles HTTPS with Let's Encrypt.

Start Caddy:
```bash
sudo systemctl start caddy
sudo systemctl enable caddy
```

### Option B: Nginx

Install Nginx:
```bash
sudo apt-get update
sudo apt-get install -y nginx
```

Create a config at `/etc/nginx/sites-available/gmail-mcp`:
```nginx
server {
    listen 80;
    server_name gmail-mcp.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name gmail-mcp.example.com;

    ssl_certificate /etc/letsencrypt/live/gmail-mcp.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/gmail-mcp.example.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8811;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the site and get an SSL cert with Certbot:
```bash
sudo ln -s /etc/nginx/sites-available/gmail-mcp /etc/nginx/sites-enabled/
sudo certbot certonly --standalone -d gmail-mcp.example.com
sudo systemctl start nginx
sudo systemctl enable nginx
```

## Step 2: Prepare Your Google Cloud Credentials

On your local machine:
1. Download `credentials.json` from Google Cloud Console (Desktop OAuth app)
2. Upload it to your server:
   ```bash
   scp secrets/credentials.json user@your-server:~/gmail-mcp-server/secrets/
   ```

Alternatively, create the file directly on the server by copy-pasting its contents.

## Step 3: Authorize Once

On your server, run the authorization flow once to generate `token.json`:

```bash
cd ~/gmail-mcp-server
python -m venv .venv
source .venv/bin/activate
pip install -e .
python authorize.py
```

This will:
1. Start a local web server
2. Open your browser to authorize the app
3. Write `secrets/token.json` once you approve

**If you can't open a browser:** Use SSH port forwarding:
```bash
# On your local machine
ssh -L 8080:localhost:8080 user@your-server

# Then visit http://localhost:8080 in your browser
```

## Step 4: Configure `.env`

On your server, create `.env` from the template:

```bash
cp .env.example .env
```

Edit `.env` with your actual values:

```env
GMAIL_MCP_CREDENTIALS=secrets/credentials.json
GMAIL_MCP_TOKEN=secrets/token.json

# Your actual domain
GMAIL_MCP_ALLOWED_HOSTS=gmail-mcp.example.com

GMAIL_MCP_ENABLE_OAUTH=1
GMAIL_MCP_ISSUER_URL=https://gmail-mcp.example.com

# Generate a stable client ID (not secret, just an identifier)
GMAIL_MCP_OAUTH_CLIENT_ID=gmail-mcp-abcd1234

# Your actual ChatGPT connector redirect URI (find in ChatGPT settings)
GMAIL_MCP_OAUTH_REDIRECT_URIS=https://chatgpt.com/connector/oauth/your_connector_id

# Generate a strong passphrase for the consent screen
# Run: python -c "import secrets; print(secrets.token_urlsafe(24))"
GMAIL_MCP_OAUTH_PASSPHRASE=your_strong_passphrase_here

GMAIL_MCP_OAUTH_STATE=secrets/oauth_state.json
```

**Never commit `.env` to git.**

## Step 5: Start the Server

```bash
docker compose up -d --build
```

Verify it's running:
```bash
docker compose ps
docker compose logs gmail-mcp
```

You should see something like:
```
gmail-mcp  | INFO:     Uvicorn running on http://0.0.0.0:8811
```

## Step 6: Test the Setup

```bash
# Test the OAuth discovery endpoint
curl https://gmail-mcp.example.com/.well-known/oauth-authorization-server

# Test the MCP endpoint
curl https://gmail-mcp.example.com/mcp
```

Both should return JSON responses.

## Step 7: Connect ChatGPT

1. In ChatGPT, go to **Settings → Tools → Developer tools → Create a new action**
2. Click **Create new connector**
3. Fill in:
   - **Name:** gmail-mcp
   - **Server URL:** `https://gmail-mcp.example.com/mcp`
   - **Authentication:** OAuth
   - **Client ID:** `gmail-mcp-abcd1234` (from your `.env`)
   - **Token endpoint auth method:** `None`
4. Save and wait for the discovery to complete
5. It will auto-find authorization and token endpoints

When you first use the connector, you'll see the consent page asking for your passphrase. Enter it, and ChatGPT will get an access token.

## Maintenance

### Updating the Server

```bash
git pull origin main
docker compose up -d --build
```

### Viewing Logs

```bash
docker compose logs gmail-mcp -f
```

### Restarting

```bash
docker compose restart gmail-mcp
```

### Updating `.env`

After editing `.env`, restart the container:
```bash
docker compose restart gmail-mcp
```

## Troubleshooting Deployment

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues like:
- Connection refused
- OAuth errors
- Passphrase not working
- Container won't start

## Security Considerations

- ✅ Only `gmail.readonly` and `gmail.compose` are requested
- ✅ Your OAuth token is stored locally in `secrets/`, never sent to us
- ✅ The passphrase protects the consent screen; a leaked URL alone can't authorize
- ✅ DNS rebinding protection via `GMAIL_MCP_ALLOWED_HOSTS`
- ✅ This is single-tenant: whoever gets past the passphrase reads *your* Gmail as *you*

**Don't share your server URL and passphrase together.** Either restrict by IP, or use a strong passphrase and keep it private.

## Monitoring

For production use, consider:
- Monitoring that the container is running: `docker-health-check` or similar
- Logs aggregation: Syslog, CloudWatch, or a log service
- Rate limiting on your reverse proxy if exposed to untrusted clients

Example with Caddy's built-in limits:
```caddy
gmail-mcp.example.com {
    rate_limit * 10r/s
    reverse_proxy localhost:8811
}
```

## Uninstalling

To stop and remove everything:
```bash
docker compose down
rm -rf secrets/  # Optional: removes cached tokens
```

Your `credentials.json` and `.env` remain for reinstalling later.

