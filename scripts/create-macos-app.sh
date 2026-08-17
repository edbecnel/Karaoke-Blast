#!/usr/bin/env bash
# Build Karaoke Blast.app and install it to /Applications.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="Karaoke Blast"
BUNDLE_ID="com.karaokeblast.app"
INSTALL_DIR="${1:-/Applications}"
APP_PATH="$INSTALL_DIR/$APP_NAME.app"
ICON_PNG="$ROOT/src/karaoke_blast/assets/icon.png"

resolve_python() {
  local candidates=(
    "$ROOT/.venv/bin/python"
    "$(command -v python3 || true)"
    "$(command -v python || true)"
  )

  for candidate in "${candidates[@]}"; do
    [[ -n "$candidate" && -x "$candidate" ]] || continue
    if "$candidate" -c "import karaoke_blast" >/dev/null 2>&1; then
      printf '%s' "$candidate"
      return 0
    fi
  done

  echo "Could not find a Python with karaoke_blast installed." >&2
  echo "Run: pip install -e \"$ROOT\"" >&2
  return 1
}

PYTHON="$(resolve_python)"
echo "Using Python: $PYTHON"

APP_VERSION="$("$PYTHON" -c "import tomllib; print(tomllib.load(open('$ROOT/pyproject.toml', 'rb'))['project']['version'])")"

BUILD_DIR="$(mktemp -d)"
trap 'rm -rf "$BUILD_DIR"' EXIT

CONTENTS="$BUILD_DIR/$APP_NAME.app/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"
mkdir -p "$MACOS" "$RESOURCES"

cat >"$MACOS/launcher" <<EOF
#!/bin/zsh
exec "$PYTHON" -m karaoke_blast "\$@"
EOF
chmod +x "$MACOS/launcher"

cat >"$CONTENTS/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>launcher</string>
  <key>CFBundleIdentifier</key>
  <string>$BUNDLE_ID</string>
  <key>CFBundleName</key>
  <string>$APP_NAME</string>
  <key>CFBundleDisplayName</key>
  <string>$APP_NAME</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>$APP_VERSION</string>
  <key>LSMinimumSystemVersion</key>
  <string>11.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
EOF

echo "Building app icon..."
"$PYTHON" "$ROOT/scripts/build_app_icon.py" "$ICON_PNG" "$RESOURCES/AppIcon.icns"

rm -rf "$APP_PATH"
mkdir -p "$INSTALL_DIR"
cp -R "$BUILD_DIR/$APP_NAME.app" "$APP_PATH"

echo "Installed $APP_PATH"
echo "Launch it from Finder, Launchpad, or Spotlight."
