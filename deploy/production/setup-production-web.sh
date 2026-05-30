#!/usr/bin/env bash
# setup-production-web.sh — stand up qbo.husband.llc on the VPS:
# Caddy + auto-TLS, static legal pages, and the OAuth callback server.
# Idempotent. Run from the laptop; it pushes to the VPS and configures it.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
VPS="${VPS:-178.156.191.113}"
SSH_KEY="${SSH_KEY:-/home/john/.ssh/cto-deploy}"
SSH="ssh -i $SSH_KEY -o StrictHostKeyChecking=accept-new -o BatchMode=yes root@$VPS"
SCP="scp -i $SSH_KEY -o StrictHostKeyChecking=accept-new"

echo "==> Installing Caddy on the VPS..."
$SSH 'command -v caddy >/dev/null || (
  apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https curl >/dev/null
  curl -1sLf "https://dl.cloudsmith.io/public/caddy/stable/gpg.key" | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf "https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt" | tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  apt-get update -qq && apt-get install -y -qq caddy
)'

echo "==> Deploying legal/landing pages to /var/www/bookie..."
$SSH 'mkdir -p /var/www/bookie'
$SCP "$HERE"/www/*.html "root@$VPS:/var/www/bookie/"

echo "==> Deploying the OAuth callback server + systemd unit..."
$SCP "$HERE/qbo_callback_server.py" "root@$VPS:/opt/openharness-deploy/qbo_callback_server.py"
$SSH 'mkdir -p /root/.config/bookie && cat > /etc/systemd/system/qbo-callback.service <<UNIT
[Unit]
Description=Bookie QBO OAuth callback server
After=network-online.target

[Service]
ExecStart=/usr/bin/python3 /opt/openharness-deploy/qbo_callback_server.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload && systemctl enable --now qbo-callback.service'

echo "==> Installing Caddyfile + starting Caddy (auto-TLS)..."
$SCP "$HERE/Caddyfile" "root@$VPS:/etc/caddy/Caddyfile"
$SSH 'systemctl enable caddy >/dev/null 2>&1; systemctl restart caddy; sleep 8; systemctl is-active caddy'

echo "==> Verifying TLS + pages (cert issuance can take ~30s on first run)..."
for i in $(seq 1 6); do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 https://qbo.husband.llc/ 2>/dev/null || echo 000)
  echo "  attempt $i: https://qbo.husband.llc/ → HTTP $CODE"
  [ "$CODE" = "200" ] && break
  sleep 10
done
echo "==> privacy page: $(curl -s -o /dev/null -w '%{http_code}' --max-time 15 https://qbo.husband.llc/privacy 2>/dev/null)"
echo "==> Done."
