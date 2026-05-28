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

echo "==> Updating employees.json paths to match this install location..."
python3 - "$HERE" <<'PY'
import json, os, sys
HERE = sys.argv[1]
p = os.path.join(HERE, "config", "employees.json")
with open(p) as f:
    d = json.load(f)
for e in d.get("employees", []):
    name = e.get("name")
    if not name:
        continue
    e["path"] = os.path.join(HERE, "employees", name)
    # Try to relocate python_module if it pointed at a now-stale path
    if e.get("python_module") and not os.path.isdir(e["python_module"]):
        candidate = os.path.abspath(os.path.join(HERE, "..", name.capitalize(), "src"))
        if os.path.isdir(candidate):
            e["python_module"] = candidate
        else:
            candidate2 = os.path.abspath(os.path.join(HERE, "..", name, "src"))
            if os.path.isdir(candidate2):
                e["python_module"] = candidate2
with open(p, "w") as f:
    json.dump(d, f, indent=2)
print(f"    Patched paths in {p}")
PY

echo "==> Running workspace integrity check..."
./bin/harness verify

echo
echo "==> OpenHarness installed."
echo "    Add to PATH:  export PATH=\"$HERE/bin:\$PATH\""
echo "    First run:    harness restart"
