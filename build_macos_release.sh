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
TARGET_ARCH="${TARGET_ARCH:-}"

if ! command -v pyinstaller >/dev/null 2>&1; then
  echo "PyInstaller is required to build the macOS app."
  echo "Install it with: python3 -m pip install pyinstaller"
  exit 1
fi

rm -rf "$BUILD_DIR" "$DIST_DIR" "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"

pyinstaller_args=(
  --noconfirm
  --clean
  --windowed
  --name "$APP_NAME"
  --osx-bundle-identifier "$BUNDLE_ID"
  --add-data "$PROJECT_DIR/sprite.png:."
)

if [[ -n "$TARGET_ARCH" ]]; then
  pyinstaller_args+=(--target-arch "$TARGET_ARCH")
fi

pyinstaller "${pyinstaller_args[@]}" "$PROJECT_DIR/pet.py"

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

echo "Built app: $APP_PATH"
echo "Release DMG: $DMG_PATH"