#!/bin/zsh
set -euo pipefail

APP_NAME="Desktop Pet"
BUNDLE_ID="com.nicolaswolf.desktoppet"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$PROJECT_DIR/build"
DIST_DIR="$PROJECT_DIR/dist"
RELEASE_DIR="$PROJECT_DIR/release"
APP_PATH="$DIST_DIR/$APP_NAME.app"
DMG_PATH="$RELEASE_DIR/Desktop-Pet-macOS.dmg"
ZIP_PATH="$RELEASE_DIR/Desktop-Pet-macOS.zip"
TARGET_ARCH="${TARGET_ARCH:-}"
# Build number baked into the bundle (and published as version.txt) so the
# in-app updater can tell whether a newer build exists. 0 for local builds.
BUILD_VERSION="${BUILD_VERSION:-0}"

if ! command -v pyinstaller >/dev/null 2>&1; then
  echo "PyInstaller is required to build the macOS app."
  echo "Install it with: python3 -m pip install pyinstaller"
  exit 1
fi

rm -rf "$BUILD_DIR" "$DIST_DIR" "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"

# Stamp this build's version into a file the app reads at runtime.
echo "$BUILD_VERSION" > "$PROJECT_DIR/VERSION"

pyinstaller_args=(
  --noconfirm
  --clean
  --windowed
  --name "$APP_NAME"
  --osx-bundle-identifier "$BUNDLE_ID"
  --add-data "$PROJECT_DIR/sprite.png:."
  --add-data "$PROJECT_DIR/VERSION:."
)

if [[ -n "$TARGET_ARCH" ]]; then
  pyinstaller_args+=(--target-arch "$TARGET_ARCH")
fi

pyinstaller "${pyinstaller_args[@]}" "$PROJECT_DIR/main.py"

STAGING_DIR="$RELEASE_DIR/dmg-staging"
rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"
cp -R "$APP_PATH" "$STAGING_DIR/"
ln -s /Applications "$STAGING_DIR/Applications"

hdiutil create \
  -volname "$APP_NAME" \
  -srcfolder "$STAGING_DIR" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

rm -rf "$STAGING_DIR"

# A zipped .app (preserving the bundle) is what the in-app updater downloads,
# plus a plain version.txt it checks first.
/usr/bin/ditto -c -k --keepParent "$APP_PATH" "$ZIP_PATH"
echo "$BUILD_VERSION" > "$RELEASE_DIR/version.txt"

echo "Built app: $APP_PATH"
echo "Release DMG: $DMG_PATH"
echo "Release ZIP: $ZIP_PATH"
echo "Version: $BUILD_VERSION"