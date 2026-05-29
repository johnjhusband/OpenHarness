#!/usr/bin/env bash
# ship-credentials.sh — copy QBO + Plaid credential files from laptop to VPS.
# Run after completing the OAuth flows locally (qbo-authorize.sh, plaid-link.sh).
set -euo pipefail

VPS="${VPS:-178.156.191.113}"
SSH_KEY="${SSH_KEY:-/home/john/.ssh/cto-deploy}"
LOCAL_CONFIG="${BOOKIE_CONFIG_ROOT:-$HOME/.config/bookie}"
REMOTE_CONFIG="/root/.config/bookie"

# accept-new = trust on first contact, refuse if the host key ever changes.
# StrictHostKeyChecking=no would silently accept MITM at any later point.
SSH_OPTS=(-i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o BatchMode=yes)

if [ ! -d "$LOCAL_CONFIG" ]; then
  echo "ERROR: $LOCAL_CONFIG not found. Run scripts/qbo-authorize.sh and scripts/plaid-link.sh first." >&2
  exit 1
fi

ssh "${SSH_OPTS[@]}" "root@$VPS" "mkdir -p $REMOTE_CONFIG && chmod 700 $REMOTE_CONFIG"

shipped_count=0
for f in qbo-credentials.json plaid-credentials.json plaid-items.json; do
  if [ -f "$LOCAL_CONFIG/$f" ]; then
    scp -q "${SSH_OPTS[@]}" "$LOCAL_CONFIG/$f" "root@$VPS:$REMOTE_CONFIG/$f"
    echo "shipped: $f"
    shipped_count=$((shipped_count + 1))
  else
    echo "skipped (not present locally): $f"
  fi
done

if [ "$shipped_count" -eq 0 ]; then
  echo "Nothing was shipped. Did you run the OAuth flows first?" >&2
  exit 1
fi

# Single chmod for all shipped files in one round-trip
ssh "${SSH_OPTS[@]}" "root@$VPS" "chmod 600 $REMOTE_CONFIG/*.json 2>/dev/null || true"

echo "Restarting daemon on VPS to pick up new credentials..."
ssh "${SSH_OPTS[@]}" "root@$VPS" "export XDG_RUNTIME_DIR=/run/user/0 && systemctl --user restart openharness-daemon.service"

# Wait for the daemon to actually load config — is-active returns 0 before Python
# has read anything; a malformed JSON would crash silently after that.
echo "Verifying daemon health post-restart..."
sleep 4
LOG="$(ssh "${SSH_OPTS[@]}" "root@$VPS" 'export XDG_RUNTIME_DIR=/run/user/0 && journalctl --user -u openharness-daemon.service --since "10 seconds ago" --no-pager' 2>&1)"
if echo "$LOG" | grep -iE 'traceback|FATAL|cannot load provider|config.*missing|json.*decode|exception' >/dev/null; then
  echo "ERROR: daemon logged errors after restart. Recent log:" >&2
  echo "$LOG" | tail -20 >&2
  exit 2
fi
STATUS="$(ssh "${SSH_OPTS[@]}" "root@$VPS" 'export XDG_RUNTIME_DIR=/run/user/0 && systemctl --user is-active openharness-daemon.service')"
if [ "$STATUS" != "active" ]; then
  echo "ERROR: daemon is not active (status=$STATUS)" >&2
  exit 2
fi
echo "Daemon active, no errors in last 10s."
echo "Done."
