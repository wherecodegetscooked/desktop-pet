"""Self-update for the downloadable (frozen) app.

When running as the packaged ``.app``, "Check for updates" asks GitHub for the
latest build number and, if it's newer and the user agrees, downloads the new
bundle, clears its quarantine flag (so macOS shows no Gatekeeper prompt on the
*update*), swaps it in, and relaunches. When running from source it falls back
to ``git pull`` via ``update.sh``.

The download/swap runs in a small detached shell script so it can finish after
the app quits — you can't replace a bundle's files while it's still running.
"""

import os
import shlex
import subprocess
import sys
import tempfile

# owner/repo whose GitHub Releases host the builds.
UPDATE_REPO = "wherecodegetscooked/desktop-pet"
# Assets live on a moving "latest" release that CI updates on every build.
_BASE = f"https://github.com/{UPDATE_REPO}/releases/download/latest"
VERSION_URL = f"{_BASE}/version.txt"
ZIP_URL = f"{_BASE}/Desktop-Pet-macOS.zip"


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def _resource_path(name):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, name)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)


def current_version():
    """This build's number (written into the bundle at build time). 0 if unknown
    (e.g. a plain source checkout), which simply means 'always older'."""
    try:
        with open(_resource_path("VERSION")) as handle:
            return int(handle.read().strip())
    except (OSError, ValueError):
        return 0


def _latest_version(timeout=8):
    # Fetch with the system curl rather than urllib: the packaged app's bundled
    # Python has no CA bundle, so HTTPS via urllib fails certificate verification.
    # curl uses macOS's trust store and always works.
    result = subprocess.run(
        ["/usr/bin/curl", "-fsSL", "--max-time", str(timeout), VERSION_URL],
        capture_output=True,
        text=True,
        timeout=timeout + 5,
    )
    if result.returncode != 0:
        raise RuntimeError(f"curl exited {result.returncode}")
    return int(result.stdout.strip())


def _bundle_path():
    """Path to the running ``.app`` bundle, or None if not bundled."""
    path = os.path.realpath(sys.executable)
    for _ in range(5):
        path = os.path.dirname(path)
        if path.endswith(".app"):
            return path
    return None


def _as_applescript(text):
    """Quote a Python string as an AppleScript string literal."""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _alert(message, buttons, default):
    """Show a native dialog and return the clicked button label (or None).

    Driven through System Events with `activate` so it reliably comes to the
    front even though the pet is a background (menu-bar-only) app — a plain
    `osascript display dialog` from such an app often never appears.
    """
    button_list = "{" + ", ".join(_as_applescript(b) for b in buttons) + "}"
    dialog = (
        f"display dialog {_as_applescript(message)} "
        f"buttons {button_list} default button {_as_applescript(default)} "
        'with title "Desktop Pet"'
    )
    lines = ["tell application \"System Events\"", "activate", dialog, "end tell"]
    args = ["osascript"]
    for line in lines:
        args += ["-e", line]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.SubprocessError):
        return None
    marker = "button returned:"
    if marker in result.stdout:
        return result.stdout.split(marker, 1)[1].strip()
    return None


def _prompt(message, default=""):
    """Native Texteingabe (System Events display dialog mit default answer).
    Gibt den eingegebenen Text zurueck, oder None bei Abbruch/Fehler."""
    dialog = (
        f"display dialog {_as_applescript(message)} "
        f"default answer {_as_applescript(default)} "
        'with title "Desktop Pet" buttons {"Abbrechen", "OK"} default button "OK"'
    )
    lines = ["tell application \"System Events\"", "activate", dialog, "end tell"]
    args = ["osascript"]
    for line in lines:
        args += ["-e", line]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None  # Abbrechen
    marker = "text returned:"
    if marker in result.stdout:
        return result.stdout.split(marker, 1)[1].strip()
    return None


_SWAP_SCRIPT = """#!/bin/zsh
set -uo pipefail
URL=__URL__
APP=__APP__
TMP="$(mktemp -d)"
cd "$TMP" || exit 1
/usr/bin/curl -fsSL "$URL" -o app.zip || exit 1
/usr/bin/ditto -x -k app.zip ex || exit 1
NEW="$(/usr/bin/find ex -maxdepth 2 -name '*.app' -type d | /usr/bin/head -n1)"
[ -n "$NEW" ] || exit 1
/usr/bin/xattr -dr com.apple.quarantine "$NEW" 2>/dev/null || true
# Wait for the running app to quit before swapping its bundle.
for _ in {1..200}; do
  /usr/bin/pgrep -f "$APP/Contents/MacOS" >/dev/null 2>&1 || break
  sleep 0.1
done
/bin/rm -rf "$APP.bak" 2>/dev/null || true
/bin/mv "$APP" "$APP.bak" 2>/dev/null || true
if /bin/mv "$NEW" "$APP"; then
  /bin/rm -rf "$APP.bak" 2>/dev/null || true
else
  /bin/mv "$APP.bak" "$APP" 2>/dev/null || true  # restore on failure
fi
/usr/bin/open -n "$APP"
"""


def _spawn_swap(bundle):
    """Write the download/swap helper to a temp file and launch it detached so
    it outlives this process (which is about to quit)."""
    script = _SWAP_SCRIPT.replace("__URL__", shlex.quote(ZIP_URL)).replace(
        "__APP__", shlex.quote(bundle)
    )
    fd, path = tempfile.mkstemp(suffix=".sh", prefix="desktoppet-update-")
    with os.fdopen(fd, "w") as handle:
        handle.write(script)
    os.chmod(path, 0o755)
    subprocess.Popen(
        ["/bin/zsh", path],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def check_for_updates(project_dir):
    """Drive the update flow. Returns one of:
    'updating'  — an update/relaunch was kicked off; the caller should quit.
    'uptodate'  — already on the latest build.
    'declined'  — newer build exists but the user chose Later.
    'failed'    — couldn't reach GitHub or locate the bundle.
    """
    if not is_frozen():
        # Source / menu-bar-wrapper install: git pull + relaunch.
        script = os.path.join(project_dir, "update.sh")
        if not os.path.exists(script):
            return "failed"
        subprocess.Popen(
            ["/bin/zsh", script],
            cwd=project_dir,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return "updating"

    current = current_version()
    try:
        latest = _latest_version()
    except Exception:
        _alert(
            "Couldn't check for updates.\n\nCheck your internet connection and "
            "try again.",
            ["OK"],
            "OK",
        )
        return "failed"
    if latest <= current:
        _alert(f"You're up to date (build {current}).", ["OK"], "OK")
        return "uptodate"
    bundle = _bundle_path()
    if not bundle:
        _alert("An update is available, but the app couldn't locate itself to "
               "replace.", ["OK"], "OK")
        return "failed"
    choice = _alert(
        f"A new version of Desktop Pet is available (build {latest}).\n\n"
        "Download and update now?",
        ["Later", "Update now"],
        "Update now",
    )
    if choice != "Update now":
        return "declined"
    _spawn_swap(bundle)
    return "updating"
