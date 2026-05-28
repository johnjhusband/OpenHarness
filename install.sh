#!/usr/bin/env bash
# install.sh — reproducible OpenHarness setup
# Per [install-must-be-reproducible-from-repo] feedback rule:
# single command produces a working harness, zero manual steps.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

echo "==> Verifying Python 3.10+..."
python3 -c "import sys; assert sys.version_info >= (3, 10), 'need Python 3.10+'"

echo "==> Making bin/harness executable..."
chmod +x bin/harness

echo "==> Initializing state directory..."
mkdir -p state state/checkpoints state/sessions

echo "==> Running workspace integrity check..."
./bin/harness verify

echo
echo "==> OpenHarness installed."
echo "    Add to PATH:  export PATH=\"$HERE/bin:\$PATH\""
echo "    First run:    harness restart"
