#!/usr/bin/env bash
# Build "Gesture Control.app" and "Gesture Control.dmg" for local use.
set -euo pipefail

cd "$(dirname "$0")"
APP_NAME="Gesture Control"
PY=".venv/bin/python"

[ -x "$PY" ] || { echo "Missing .venv - create it and install requirements.txt first."; exit 1; }
[ -f hand_landmarker.task ] || { echo "Missing hand_landmarker.task in the project folder."; exit 1; }

"$PY" -m pip install --quiet pyinstaller

rm -rf build dist "$APP_NAME.spec" "$APP_NAME.dmg" dmg_staging

"$PY" -m PyInstaller --noconfirm --windowed --name "$APP_NAME" \
  --osx-bundle-identifier local.gesturecontrol \
  --collect-all mediapipe \
  --hidden-import rumps \
  --hidden-import AppKit \
  --add-data "hand_landmarker.task:." \
  launch_menubar.py

# Camera permission text is required, or macOS denies the camera / kills the app.
/usr/libexec/PlistBuddy -c "Add :NSCameraUsageDescription string 'Uses the camera to see hand gestures.'" \
  "dist/$APP_NAME.app/Contents/Info.plist"

# Menu bar app: no Dock icon.
/usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "dist/$APP_NAME.app/Contents/Info.plist"

# Editing the plist invalidates the signature: re-sign ad-hoc (no paid account needed).
codesign --force --deep --sign - "dist/$APP_NAME.app"

# DMG with an Applications shortcut for drag-install.
mkdir dmg_staging
cp -R "dist/$APP_NAME.app" dmg_staging/
ln -s /Applications dmg_staging/Applications
hdiutil create -volname "$APP_NAME" -srcfolder dmg_staging -ov -format UDZO "$APP_NAME.dmg"
rm -rf dmg_staging

echo "Done: $APP_NAME.dmg"
