# EC2 + Cloudflare Tunnel Deployment

> Run Claude Code on this EC2 instance to execute these steps interactively.

## Prerequisites

- EC2 `t3.medium`, Ubuntu 22.04 LTS, 50GB gp3
- Security group: port 22 (SSH) only — Cloudflare Tunnel handles HTTPS
- `.env` created at repo root with `GOOGLE_API_KEY`, `ELEVENLABS_API_KEY`, `VIBECUT_ENV=production`

---

## 1. System Dependencies

```bash
sudo apt update && sudo apt install -y \
  python3.11 python3.11-venv python3-pip \
  ffmpeg \
  nodejs npm \
  git
```

## 2. App Setup

```bash
git clone https://github.com/<user>/gemini-vibecut.git ~/gemini-vibecut
cd ~/gemini-vibecut
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd remotion && npm install && cd ..
```

## 3. Create `.env`

```bash
cat > ~/gemini-vibecut/.env << 'EOF'
GOOGLE_API_KEY=<your-key>
ELEVENLABS_API_KEY=<your-key>
VIBECUT_ENV=production
EOF
```

## 4. systemd Service

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
ExecStart=/home/ubuntu/gemini-vibecut/.venv/bin/python api_server.py
Restart=always
RestartSec=5
Environment=PATH=/home/ubuntu/gemini-vibecut/.venv/bin:/usr/local/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable vibecut
sudo systemctl start vibecut
```

Verify: `curl -s http://localhost:8000/health`

## 5. Cloudflare Tunnel (Named)

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

Create config:
```bash
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/config.yml << 'EOF'
tunnel: vibecut
credentials-file: /home/ubuntu/.cloudflared/<TUNNEL_ID>.json
ingress:
  - hostname: vibecut.<your-domain>.com
    service: http://localhost:8000
  - service: http_status:404
EOF
```

Route DNS + start:
```bash
cloudflared tunnel route dns vibecut vibecut.<your-domain>.com
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

## 6. Deploy Script

```bash
cat > ~/deploy.sh << 'SCRIPT'
#!/bin/bash
set -e
cd /home/ubuntu/gemini-vibecut
git pull origin main
source .venv/bin/activate
pip install -q -r requirements.txt
cd remotion && npm install --quiet && cd ..
sudo systemctl restart vibecut
sleep 3
curl -sf http://localhost:8000/health && echo " Deploy OK" || echo " Deploy FAILED"
SCRIPT
chmod +x ~/deploy.sh
```

## 7. Session Cleanup Cron

```bash
(crontab -l 2>/dev/null; echo "0 3 * * * find /home/ubuntu/gemini-vibecut/assets/outputs/sessions/ -maxdepth 1 -mtime +3 -exec rm -rf {} \;") | crontab -
```

---

## Verification Checklist

1. `curl https://vibecut.<domain>.com/health` returns healthy
2. Browser: demo loads with phone frame UI
3. Upload a photo, streaming analysis works through tunnel
4. Create character, image generation returns
5. Generate manga, streaming panels work
6. Animate story, full video pipeline completes (~2-5 min SSE)
7. Second browser tab gets independent session

## Redeploy (from laptop)

```bash
alias deploy-vibecut="ssh ec2-vibecut 'bash /home/ubuntu/deploy.sh'"
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
