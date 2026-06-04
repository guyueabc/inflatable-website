#!/bin/bash
# ============================================================================
#  HK API Proxy Deployment — Alibaba Cloud HK Lightweight (Ubuntu 22.04+)
#  Run as root on a fresh server.
# ============================================================================
set -e

APP_DIR="/opt/inflatable-hk"
echo "=== InflatableModel HK API Proxy Deployment ==="

# 1. System packages
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv curl

# 2. Create app user & dirs
id -u www-data &>/dev/null || useradd -r -s /bin/false www-data
mkdir -p "$APP_DIR"
chown -R www-data:www-data "$APP_DIR"

# 3. Copy only proxy files
cp /root/inflatable-website/hk_proxy.py "$APP_DIR/"
cp /root/inflatable-website/requirements.txt "$APP_DIR/"

# 4. Python venv
python3 -m venv "$APP_DIR/venv"
source "$APP_DIR/venv/bin/activate"
pip install --upgrade pip flask requests gunicorn

# 5. Create minimal .env for HK proxy
cat > "$APP_DIR/.env" << 'ENVEOF'
HUNYUAN_API_KEY=sk-kuuLt0xbnfj43TOlJ75EmlgY7vQbmAkz7w4aR9giDL78HtzX
HUNYUAN_ENDPOINT=https://api.ai3d.cloud.tencent.com
PROXY_SECRET=REPLACE_WITH_RANDOM_SECRET
PORT=8080
ENVEOF
chmod 600 "$APP_DIR/.env"
chown www-data:www-data "$APP_DIR/.env"

# 6. systemd service
cp /root/inflatable-website/deploy/inflatable-hk.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable inflatable-hk
systemctl start inflatable-hk

echo ""
echo "=== HK API Proxy deployed ==="
echo "Check status:  systemctl status inflatable-hk"
echo "Check logs:    journalctl -u inflatable-hk -f"
echo "Test:          curl http://127.0.0.1:8080/health"
echo ""
echo "⚠️  IMPORTANT — edit $APP_DIR/.env and replace PROXY_SECRET with a real secret!"
echo "⚠️  Then configure CloudFlare Tunnel to expose port 8080."
