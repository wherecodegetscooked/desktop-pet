#!/bin/zsh
# One-time setup for a new machine (e.g. a friend's Mac).
#
# Creates the virtualenv, installs dependencies, and installs the menu-bar app
# that autostarts. After this, never touch the terminal again: use the pet and
# click the paw in the menu bar -> "Update to latest" to get new versions.
set -euo pipefail

PROJ="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJ"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required. Install it from https://www.python.org/downloads/"
  echo "and run ./setup.sh again."
  exit 1
fi

if [[ ! -x .venv/bin/python ]]; then
  echo "Creating virtualenv…"
  python3 -m venv .venv
fi
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

./install_macos_app.sh

echo
echo "All set! The pet is installed in ~/Applications and will autostart."
echo "To get new versions later, click the paw in the menu bar -> Update to latest."
