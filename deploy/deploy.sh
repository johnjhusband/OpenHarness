#!/usr/bin/env bash
# deploy.sh — end-to-end deployment from laptop.
# Provisions the VPS, ships credentials + bootstrap, runs a smoke test.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
log() { echo "[deploy] $*" >&2; }

# 1. Provision the VPS
log "Provisioning VPS..."
VPS_IP="$(bash "$HERE/provision-vps.sh")"
log "VPS at $VPS_IP"

SSH_KEY="/home/john/.ssh/cto-deploy"
SSH_OPTS="-i $SSH_KEY -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10"

# 2. Read credentials from laptop
CREDS="$(cat /home/john/.claude/.credentials.json)"
GITHUB_TOKEN_VAL="$(grep -h '^GITHUB_TOKEN' /home/john/repos/CTO/.env 2>/dev/null | cut -d= -f2-)"

# 3. Ship the bootstrap script + credentials, then run
log "Shipping bootstrap to VPS..."
scp $SSH_OPTS "$HERE/bootstrap-vps.sh" "root@$VPS_IP:/tmp/bootstrap-vps.sh" >&2

log "Shipping credentials to VPS (encrypted in transit only)..."
printf '%s' "$CREDS" | ssh $SSH_OPTS "root@$VPS_IP" 'cat > /tmp/claude-credentials.json && chmod 600 /tmp/claude-credentials.json'

log "Running bootstrap..."
ssh $SSH_OPTS "root@$VPS_IP" "GITHUB_USER=johnjhusband GITHUB_TOKEN='$GITHUB_TOKEN_VAL' bash /tmp/bootstrap-vps.sh"

log "Done. VPS_IP=$VPS_IP"
echo "$VPS_IP"
