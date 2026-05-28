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

echo "==> Scaffolding / patching config/employees.json for this install location..."
python3 - "$HERE" <<'PY'
import json, os, sys
HERE = sys.argv[1]
live = os.path.join(HERE, "config", "employees.json")
template = os.path.join(HERE, "config", "employees.template.json")
if not os.path.exists(live):
    with open(template) as f:
        d = json.load(f)
    print(f"    Scaffolded {live} from template")
else:
    with open(live) as f:
        d = json.load(f)
for e in d.get("employees", []):
    name = e.get("name")
    if not name:
        continue
    # path is workspace-relative in the template ("employees/bookie") OR an absolute
    # path from a prior install. Always rewrite to absolute under this $HERE.
    p_in = e.get("path", f"employees/{name}")
    e["path"] = os.path.abspath(p_in if os.path.isabs(p_in) else os.path.join(HERE, p_in))
    # python_module is OpenHarness-relative ("../Bookie/src") OR absolute.
    pm_in = e.get("python_module")
    if pm_in:
        pm = pm_in if os.path.isabs(pm_in) else os.path.abspath(os.path.join(HERE, pm_in))
        if not os.path.isdir(pm):
            # Try sibling clone fallback under $HERE/..
            candidate = os.path.abspath(os.path.join(HERE, "..", name.capitalize(), "src"))
            if os.path.isdir(candidate):
                pm = candidate
        e["python_module"] = pm
with open(live, "w") as f:
    json.dump(d, f, indent=2)
print(f"    Wrote {live}")
PY

echo "==> Running workspace integrity check..."
./bin/harness verify

echo
echo "==> OpenHarness installed."
echo "    Add to PATH:  export PATH=\"$HERE/bin:\$PATH\""
echo "    First run:    harness restart"
