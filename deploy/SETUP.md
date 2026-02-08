# EC2 + Cloudflare Tunnel Deployment

> Gemini VibeCut runs on EC2 with Cloudflare Tunnel for HTTPS.

## Live URL

**https://vibecut.whatif.art** — served via Cloudflare Tunnel

## Instance Details

- **Host:** `jiao-gemini3-hackathon` (SSH config on laptop)
- **IP:** `54.202.202.158`
- **OS:** Ubuntu 24.04 LTS, `t3.medium`, us-west-2
- **SSH key:** `jiao-ec2.pem`
- **Domain:** `whatif.art` (Cloudflare-managed)

## Current State

| Component | Status | Location |
|-----------|--------|----------|
| Python 3.11.14 | Installed (via uv) | `~/whatif/bin/python` |
| uv 0.10 | Installed | `~/.local/bin/uv` |
| Node.js 22 | Installed | `/usr/bin/node` |
| FFmpeg | Installed | system |
| AWS CLI v2 | Installed | `/usr/local/bin/aws` |
| GitHub CLI (`gh`) | Authenticated | `/usr/bin/gh` |
| Claude Code | Working (Bedrock Opus 4.6) | `~/.local/bin/claude` |
| Repo | Cloned | `~/gemini-vibecut` |
| Python deps | Installed via uv | `~/whatif` venv |
| Remotion deps | Installed | `~/gemini-vibecut/remotion/node_modules` |
| `~/.claude/` config | Synced from laptop | CLAUDE.md, settings, commands, skills |
| AWS credentials | Synced (`nuva-aws` profile) | `~/.aws/` |
| cloudflared v2026.2.0 | Installed (deb) | `/usr/bin/cloudflared` |
| Tunnel `vibecut` | Active (4x QUIC) | `~/.cloudflared/` + `/etc/cloudflared/` |
| `vibecut.service` | enabled + running | `/etc/systemd/system/vibecut.service` |
| `cloudflared.service` | enabled + running | `/etc/systemd/system/cloudflared.service` |

## Services

Both services are enabled and survive reboots.

```bash
# Check status
sudo systemctl status vibecut
sudo systemctl status cloudflared

# Restart after code changes
sudo systemctl restart vibecut

# View logs
sudo journalctl -u vibecut -f
sudo journalctl -u cloudflared -f
```

### vibecut.service

```ini
[Unit]
Description=Gemini VibeCut API Server
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/gemini-vibecut/ui
EnvironmentFile=/home/ubuntu/gemini-vibecut/.env
ExecStart=/home/ubuntu/whatif/bin/python api_server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Cloudflare Tunnel Config

```yaml
# /etc/cloudflared/config.yml
tunnel: 13f82ad9-dbb1-410a-a789-9beb2ca8d34a
credentials-file: /etc/cloudflared/13f82ad9-dbb1-410a-a789-9beb2ca8d34a.json

ingress:
  - hostname: vibecut.whatif.art
    service: http://localhost:8000
    originRequest:
      noTLSVerify: true
  - service: http_status:404
```

## Cloudflare WAF Configuration

Bot Fight Mode is active zone-wide on `whatif.art`. A custom WAF skip rule allows
`vibecut.whatif.art` through without managed challenges:

- **Rule:** Hostname equals `vibecut.whatif.art` → Skip all remaining custom rules + Super Bot Fight Mode
- **Location:** Dashboard → whatif.art → Security → WAF → Custom rules

## Redeploy

```bash
# From laptop
alias deploy-vibecut="ssh jiao-gemini3-hackathon 'bash /home/ubuntu/deploy.sh'"
# Usage: git push && deploy-vibecut
```

Deploy script (`~/deploy.sh`):
```bash
#!/bin/bash
set -e
cd /home/ubuntu/gemini-vibecut
git pull origin main
~/.local/bin/uv pip install --python ~/whatif/bin/python -q -r requirements.txt
cd remotion && npm install --quiet && cd ..
sudo systemctl restart vibecut
sleep 3
curl -sf http://localhost:8000/health && echo "Deploy OK" || echo "Deploy FAILED"
```

## Verification Checklist

1. `curl https://vibecut.whatif.art/health` returns healthy
2. Browser: demo loads with phone frame UI
3. Upload a photo, streaming analysis works through tunnel
4. Create character, image generation returns
5. Generate manga, streaming panels work
6. Animate story, full video pipeline completes via SSE
7. Second browser tab gets independent session

## Architecture

```
Browser --HTTPS--> Cloudflare Edge (whatif.art)
                       |
                   WAF skip rule (vibecut.whatif.art)
                       |
                   Cloudflare Tunnel (vibecut, 4x QUIC)
                       |
                   EC2:8000 (FastAPI)
                       ├── Static files (demo.html, agent/*.js, assets/)
                       ├── API endpoints (/api/*)
                       ├── FFmpeg (subprocess)
                       └── Remotion (npx subprocess)
```

## Cost: ~$30 for 3 weeks

EC2 t3.medium on-demand (~$25) + EBS 50GB ($4) + Cloudflare Tunnel (free)
