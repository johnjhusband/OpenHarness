#!/usr/bin/env bash
# provision-vps.sh — provision a Hetzner VPS for OpenHarness daemon
# Idempotent: re-running returns the existing server's IP without creating a new one.
#
# Reads HCLOUD_TOKEN from env or from /home/john/repos/CTO/.env.
# Prints the server IPv4 to stdout. Logs go to stderr.

set -euo pipefail

SERVER_NAME="${SERVER_NAME:-bookie-v1}"
SERVER_TYPE="${SERVER_TYPE:-cpx11}"           # 2 vCPU x86, 2GB RAM, $6.99/mo
SERVER_IMAGE="${SERVER_IMAGE:-ubuntu-24.04}"
SERVER_LOCATION="${SERVER_LOCATION:-ash}"    # Ashburn, VA (closest to QBO/Plaid)
SSH_KEY_NAME="${SSH_KEY_NAME:-cto-agent-deploy}"

log() { echo "[provision] $*" >&2; }

# Load HCLOUD_TOKEN from .env if not in env
if [ -z "${HCLOUD_TOKEN:-}" ]; then
  if [ -f /home/john/repos/CTO/.env ]; then
    HCLOUD_TOKEN="$(grep -h '^HETZNER_API_TOKEN' /home/john/repos/CTO/.env | cut -d= -f2)"
  fi
fi
if [ -z "${HCLOUD_TOKEN:-}" ]; then
  echo "ERROR: HCLOUD_TOKEN not set and not found in /home/john/repos/CTO/.env" >&2
  exit 1
fi
export HCLOUD_TOKEN

# Idempotency: return existing server if it exists
existing_ip="$(hcloud server list -o noheader -o columns=name,ipv4 2>/dev/null | awk -v n="$SERVER_NAME" '$1==n {print $2}')"
if [ -n "$existing_ip" ]; then
  log "Server $SERVER_NAME already exists at $existing_ip; reusing."
  echo "$existing_ip"
  exit 0
fi

log "Creating Hetzner server: name=$SERVER_NAME type=$SERVER_TYPE image=$SERVER_IMAGE location=$SERVER_LOCATION key=$SSH_KEY_NAME"
hcloud server create \
  --name "$SERVER_NAME" \
  --type "$SERVER_TYPE" \
  --image "$SERVER_IMAGE" \
  --location "$SERVER_LOCATION" \
  --ssh-key "$SSH_KEY_NAME" \
  --label purpose=openharness-bookie \
  >&2

new_ip="$(hcloud server list -o noheader -o columns=name,ipv4 | awk -v n="$SERVER_NAME" '$1==n {print $2}')"
if [ -z "$new_ip" ]; then
  log "ERROR: created server but cannot retrieve IPv4"
  exit 1
fi
log "Created. IPv4: $new_ip"

log "Waiting for SSH to be reachable..."
for i in $(seq 1 30); do
  if ssh -i /home/john/.ssh/cto-deploy -o StrictHostKeyChecking=accept-new -o ConnectTimeout=4 -o BatchMode=yes "root@$new_ip" 'echo ready' >/dev/null 2>&1; then
    log "SSH ready after ${i} attempts."
    echo "$new_ip"
    exit 0
  fi
  sleep 5
done
log "ERROR: SSH did not become ready within 150s"
exit 2
