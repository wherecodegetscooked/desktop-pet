#!/bin/zsh
# Run the desktop pet straight from source — the simple update loop.
#
# No build, no DMG, no download, and no Gatekeeper "allow" step: because the
# code runs locally (never downloaded), macOS doesn't quarantine it. To get the
# latest after changes, just run this again. Ctrl-C to quit.
set -euo pipefail

PROJ="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJ"

# Pull the latest if this clone tracks a remote (harmless no-op if it doesn't,
# or if you're already up to date because you edit here).
git pull --ff-only 2>/dev/null || true

# Make sure the virtualenv and dependencies are in place.
if [[ ! -x .venv/bin/python ]]; then
  echo "Creating virtualenv…"
  python3 -m venv .venv
fi
.venv/bin/pip install -q -r requirements.txt

# Stop any pet that's already running (source run or the installed app), then
# launch the freshest copy.
pkill -f "$PROJ/main.py" 2>/dev/null || true
sleep 0.3

echo "Starting Desktop Pet (Ctrl-C to quit)…"
exec "$PROJ/.venv/bin/python" "$PROJ/main.py"
