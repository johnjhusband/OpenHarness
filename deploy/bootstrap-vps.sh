#!/usr/bin/env bash
# bootstrap-vps.sh — runs ON the VPS to install OpenHarness + Bookie + Claude Code
# Idempotent.
#
# Expected environment:
#   GITHUB_USER, GITHUB_TOKEN — for HTTPS git push back to origin
#   CLAUDE_CREDENTIALS_JSON   — the .credentials.json contents (passed via stdin or file)

set -euo pipefail

log() { echo "[bootstrap] $*" >&2; }

# 1. System deps
log "Installing apt deps..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git python3 python3-pip python3-venv curl ca-certificates sqlite3

# 2. Create operator user (no need; we'll use root for v1)

# 3. Install Claude Code
if ! command -v claude >/dev/null 2>&1; then
  log "Installing Claude Code via Anthropic install script..."
  curl -fsSL https://claude.ai/install.sh | bash || curl -fsSL https://claude.com/install.sh | bash
fi
if ! command -v claude >/dev/null 2>&1; then
  # fallback path
  if [ -x /root/.local/bin/claude ]; then
    export PATH="/root/.local/bin:$PATH"
  fi
fi
log "claude version: $(claude --version 2>&1 || echo 'NOT FOUND')"

# 4. Install Claude Code credentials (passed via env or file)
mkdir -p /root/.claude
if [ -n "${CLAUDE_CREDENTIALS_JSON:-}" ]; then
  log "Writing ~/.claude/.credentials.json from env"
  printf '%s' "$CLAUDE_CREDENTIALS_JSON" > /root/.claude/.credentials.json
  chmod 600 /root/.claude/.credentials.json
elif [ -f /tmp/claude-credentials.json ]; then
  log "Writing ~/.claude/.credentials.json from /tmp/claude-credentials.json"
  cp /tmp/claude-credentials.json /root/.claude/.credentials.json
  chmod 600 /root/.claude/.credentials.json
  rm /tmp/claude-credentials.json
fi

# 5. Clone repos (HTTPS for read; we'll set push URL with token below)
mkdir -p /opt/openharness-deploy
cd /opt/openharness-deploy
for repo in OpenHarness Bookie; do
  if [ ! -d "$repo" ]; then
    log "Cloning $repo..."
    git clone -q "https://github.com/${GITHUB_USER:-johnjhusband}/$repo.git"
  else
    log "Pulling $repo..."
    (cd "$repo" && git pull -q)
  fi
done

# 6. Configure git push auth if a token was provided
if [ -n "${GITHUB_TOKEN:-}" ] && [ -n "${GITHUB_USER:-}" ]; then
  log "Configuring git push auth via GITHUB_TOKEN..."
  for repo in OpenHarness Bookie; do
    (cd "/opt/openharness-deploy/$repo" && \
      git remote set-url origin "https://${GITHUB_USER}:${GITHUB_TOKEN}@github.com/${GITHUB_USER}/${repo}.git" && \
      git config user.email "bookie@husband.llc" && \
      git config user.name "Bookie (via OpenHarness VPS)")
  done
fi

# 7. Run installers
log "Installing OpenHarness..."
(cd /opt/openharness-deploy/OpenHarness && bash install.sh)
log "Installing Bookie..."
OPENHARNESS_ROOT=/opt/openharness-deploy/OpenHarness \
  bash /opt/openharness-deploy/Bookie/install.sh

# 8. Update OpenHarness employees.json to point at the VPS paths for Bookie
python3 <<'PY'
import json
p = "/opt/openharness-deploy/OpenHarness/config/employees.json"
with open(p) as f: d = json.load(f)
for e in d["employees"]:
    if e["name"] == "bookie":
        e["path"] = "/opt/openharness-deploy/OpenHarness/employees/bookie"
        e["python_module"] = "/opt/openharness-deploy/Bookie/src"
with open(p, "w") as f: json.dump(d, f, indent=2)
print("[bootstrap] employees.json updated for VPS paths")
PY

# 9. systemd --user unit (deferred unless we explicitly enable lingering;
#    for now we provide the unit file and instructions; the smoke test runs
#    `harness daemon --once` directly)
mkdir -p /root/.config/systemd/user
cat > /root/.config/systemd/user/openharness-daemon.service <<'EOF'
[Unit]
Description=OpenHarness daemon — runs AI employees on schedule
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/openharness-deploy/OpenHarness
Environment=PATH=/root/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/opt/openharness-deploy/OpenHarness/bin/harness daemon --interval 60
Restart=on-failure
RestartSec=15s

[Install]
WantedBy=default.target
EOF

log "Bootstrap complete."
log "OpenHarness at /opt/openharness-deploy/OpenHarness"
log "Bookie at /opt/openharness-deploy/Bookie"
log "systemd unit at /root/.config/systemd/user/openharness-daemon.service"
log "To run a single tick now: /opt/openharness-deploy/OpenHarness/bin/harness daemon --once --no-git-sync"
