#!/bin/bash
# ============================================================================
#  US Main Site Deployment — Vultr/DigitalOcean (Ubuntu 22.04+)
#  Run as root on a fresh VPS.
# ============================================================================
set -e

APP_DIR="/opt/inflatable-website"
echo "=== InflatableModel US Main Site Deployment ==="

# 1. System packages
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv nginx git

# 2. Create app user & dirs
id -u www-data &>/dev/null || useradd -r -s /bin/false www-data
mkdir -p "$APP_DIR" /var/log/inflatable
chown -R www-data:www-data "$APP_DIR" /var/log/inflatable

# 3. Copy project files (assumes repo is in /root/inflatable-website)
rsync -av --exclude 'deploy/' --exclude '__pycache__/' --exclude '*.db*' \
      --exclude 'flask_session/' --exclude 'backups/' --exclude 'ngrok.exe' \
      /root/inflatable-website/ "$APP_DIR/"

# 4. Python venv
python3 -m venv "$APP_DIR/venv"
source "$APP_DIR/venv/bin/activate"
pip install --upgrade pip
pip install -r "$APP_DIR/requirements.txt"

# 5. Place .env (create manually before running this script)
if [ -f /root/inflatable-website/.env ]; then
    cp /root/inflatable-website/.env "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
    chown www-data:www-data "$APP_DIR/.env"
else
    echo "⚠️  No .env found — create $APP_DIR/.env manually before starting the service."
fi

# 6. Fix ownership
chown -R www-data:www-data "$APP_DIR"

# 7. systemd service
cp /root/inflatable-website/deploy/inflatable-us.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable inflatable-us

# 8. Nginx
cp /root/inflatable-website/deploy/nginx-us.conf /etc/nginx/sites-available/inflatable
ln -sf /etc/nginx/sites-available/inflatable /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# 9. Start
systemctl start inflatable-us
echo ""
echo "=== US Main Site deployed ==="
echo "Check status:  systemctl status inflatable-us"
echo "Check logs:    journalctl -u inflatable-us -f"
echo "Next: configure CloudFlare DNS to point to this server's IP"
