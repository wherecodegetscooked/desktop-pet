#!/bin/zsh
set -euo pipefail

APP_NAME="Desktop Pet"
BUNDLE_ID="com.nicolaswolf.desktoppet"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
PET_SCRIPT="$PROJECT_DIR/main.py"
APP_DIR="$HOME/Applications/$APP_NAME.app"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
EXECUTABLE="$MACOS_DIR/DesktopPet"
PLIST="$HOME/Library/LaunchAgents/$BUNDLE_ID.plist"
LOG_DIR="$HOME/Library/Logs"
LOG_FILE="$LOG_DIR/DesktopPet.log"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing virtualenv Python at: $PYTHON_BIN"
  echo "Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

mkdir -p "$MACOS_DIR" "$RESOURCES_DIR" "$HOME/Applications" "$HOME/Library/LaunchAgents" "$LOG_DIR"

cat > "$EXECUTABLE" <<EOF
#!/bin/zsh
cd "$PROJECT_DIR"
exec "$PYTHON_BIN" "$PET_SCRIPT" >> "$LOG_FILE" 2>&1
EOF
chmod +x "$EXECUTABLE"

cat > "$CONTENTS_DIR/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>$APP_NAME</string>
  <key>CFBundleDisplayName</key>
  <string>$APP_NAME</string>
  <key>CFBundleIdentifier</key>
  <string>$BUNDLE_ID</string>
  <key>CFBundleExecutable</key>
  <string>DesktopPet</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleVersion</key>
  <string>1.0</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.0</string>
  <key>LSUIElement</key>
  <true/>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
EOF

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$BUNDLE_ID</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/open</string>
    <string>-n</string>
    <string>$APP_DIR</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$LOG_FILE</string>
  <key>StandardErrorPath</key>
  <string>$LOG_FILE</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/$BUNDLE_ID"

echo "Installed: $APP_DIR"
echo "Autostart enabled: $PLIST"
echo "Log file: $LOG_FILE"
