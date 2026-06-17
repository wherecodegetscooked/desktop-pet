#!/bin/zsh
# Pull the latest source and relaunch the pet.
#
# Invoked by the menu-bar "Update to latest" button: the running app quits, then
# this waits for it to exit, pulls the newest code, refreshes dependencies, and
# brings the pet back. Because everything runs from the local clone (never
# downloaded), there is no Gatekeeper / "allow" prompt.
set -uo pipefail

PROJ="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJ"

# Wait (up to ~6s) for the current pet to exit so the relaunch is clean.
for _ in {1..60}; do
  pgrep -f "$PROJ/main.py" >/dev/null 2>&1 || break
  sleep 0.1
done

# Fetch the newest version. Failures (no git, offline) just relaunch as-is.
git pull --ff-only 2>/dev/null || true
if [[ -x .venv/bin/python ]]; then
  .venv/bin/pip install -q -r requirements.txt 2>/dev/null || true
fi

# Relaunch: prefer the installed menu-bar app, otherwise run from source.
APP="$HOME/Applications/Desktop Pet.app"
if [[ -d "$APP" ]]; then
  open -n "$APP"
else
  nohup "$PROJ/.venv/bin/python" "$PROJ/main.py" >/dev/null 2>&1 &
fi
