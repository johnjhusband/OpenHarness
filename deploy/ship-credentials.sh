#!/usr/bin/env bash
# ship-credentials.sh — copy QBO + Plaid credential files from laptop to VPS.
# Run after completing the OAuth flows locally (qbo-authorize.sh, plaid-link.sh).
set -euo pipefail

VPS="${VPS:-178.156.191.113}"
SSH_KEY="${SSH_KEY:-/home/john/.ssh/cto-deploy}"
LOCAL_CONFIG="${BOOKIE_CONFIG_ROOT:-$HOME/.config/bookie}"
REMOTE_CONFIG="/root/.config/bookie"

if [ ! -d "$LOCAL_CONFIG" ]; then
  echo "ERROR: $LOCAL_CONFIG not found. Run scripts/qbo-authorize.sh and scripts/plaid-link.sh first." >&2
  exit 1
fi

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "root@$VPS" "mkdir -p $REMOTE_CONFIG && chmod 700 $REMOTE_CONFIG"

for f in qbo-credentials.json plaid-credentials.json plaid-items.json; do
  if [ -f "$LOCAL_CONFIG/$f" ]; then
    scp -q -i "$SSH_KEY" -o StrictHostKeyChecking=no \
      "$LOCAL_CONFIG/$f" "root@$VPS:$REMOTE_CONFIG/$f"
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "root@$VPS" "chmod 600 $REMOTE_CONFIG/$f"
    echo "shipped: $f"
  else
    echo "skipped (not present locally): $f"
  fi
done

echo "Restarting daemon on VPS to pick up new credentials..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "root@$VPS" \
  "export XDG_RUNTIME_DIR=/run/user/0 && systemctl --user restart openharness-daemon.service && systemctl --user is-active openharness-daemon.service"

echo "Done."
