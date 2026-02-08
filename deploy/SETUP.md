# EC2 + Cloudflare Tunnel Deployment

> Run Claude Code on this EC2 instance to execute these steps interactively.

## Instance Details

- **Host:** `jiao-gemini3-hackathon` (SSH config on laptop)
- **IP:** `54.202.202.158`
- **OS:** Ubuntu 24.04 LTS, `t3.medium`, us-west-2
- **SSH key:** `jiao-ec2.pem`
- **Domain:** `whatif.art` (Cloudflare-managed)

## Current State (what's already done)

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

## Remaining Steps

### 1. Create `.env`

```bash
cat > ~/gemini-vibecut/.env << 'EOF'
GOOGLE_API_KEY=<your-key>
ELEVENLABS_API_KEY=<your-key>
VIBECUT_ENV=production
EOF
```

### 2. systemd Service

```bash
sudo tee /etc/systemd/system/vibecut.service << 'EOF'
[Unit]
Description=Gemini VibeCut
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/gemini-vibecut/ui
EnvironmentFile=/home/ubuntu/gemini-vibecut/.env
ExecStart=/home/ubuntu/whatif/bin/python api_server.py
Restart=always
RestartSec=5
Environment=PATH=/home/ubuntu/whatif/bin:/home/ubuntu/.local/bin:/usr/local/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable vibecut
sudo systemctl start vibecut
```

Verify: `curl -s http://localhost:8000/health`

### 3. Cloudflare Tunnel (Named — on whatif.art)

```bash
# Install cloudflared
sudo curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
  -o /usr/local/bin/cloudflared
sudo chmod +x /usr/local/bin/cloudflared

# Auth + create tunnel
cloudflared tunnel login
cloudflared tunnel create vibecut
# Note the <TUNNEL_ID> from output
```

Create config (use a random subdomain for privacy):
```bash
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/config.yml << 'EOF'
tunnel: vibecut
credentials-file: /home/ubuntu/.cloudflared/<TUNNEL_ID>.json
ingress:
  - hostname: <random-prefix>.whatif.art
    service: http://localhost:8000
  - service: http_status:404
EOF
```

Route DNS + start:
```bash
cloudflared tunnel route dns vibecut <random-prefix>.whatif.art
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

### 4. Deploy Script

```bash
cat > ~/deploy.sh << 'SCRIPT'
#!/bin/bash
set -e
cd /home/ubuntu/gemini-vibecut
git pull origin main
source ~/whatif/bin/activate
uv pip install -q -r requirements.txt
cd remotion && npm install --quiet && cd ..
sudo systemctl restart vibecut
sleep 3
curl -sf http://localhost:8000/health && echo " Deploy OK" || echo " Deploy FAILED"
SCRIPT
chmod +x ~/deploy.sh
```

### 5. Session Cleanup Cron

```bash
(crontab -l 2>/dev/null; echo "0 3 * * * find /home/ubuntu/gemini-vibecut/assets/outputs/sessions/ -maxdepth 1 -mtime +3 -exec rm -rf {} \;") | crontab -
```

---

## Verification Checklist

1. `curl https://<random-prefix>.whatif.art/health` returns healthy
2. Browser: demo loads with phone frame UI
3. Upload a photo, streaming analysis works through tunnel
4. Create character, image generation returns
5. Generate manga, streaming panels work
6. Animate story, full video pipeline completes (~2-5 min SSE)
7. Second browser tab gets independent session

## Redeploy (from laptop)

```bash
alias deploy-vibecut="ssh jiao-gemini3-hackathon 'bash /home/ubuntu/deploy.sh'"
# Usage: git push && deploy-vibecut
```

## Architecture

```
Browser --HTTPS--> Cloudflare Edge --Tunnel--> EC2:8000 (FastAPI)
                                                ├── Static files (demo.html, agent/*.js, assets/)
                                                ├── API endpoints (/api/*)
                                                ├── FFmpeg (subprocess)
                                                └── Remotion (npx subprocess)
```

## Cost: ~$30 for 3 weeks

EC2 t3.medium on-demand (~$25) + EBS 50GB ($4) + Cloudflare Tunnel (free)
