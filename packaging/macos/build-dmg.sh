#!/usr/bin/env bash
# Build Karaoke Blast.app with a private Python runtime and create a .dmg installer.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STAGING="$SCRIPT_DIR/staging"
DIST="$SCRIPT_DIR/dist"
VERSIONS_FILE="$ROOT/packaging/common/versions.env"
APP_NAME="Karaoke Blast"
# Build paths must not contain spaces: venv ensurepip aborts on macOS (SIGABRT).
BUILD_APP_BUNDLE="KaraokeBlast.app"
BUNDLE_ID="com.karaokeblast.app"
ICON_PNG="$ROOT/src/karaoke_blast/assets/icon.png"

# shellcheck disable=SC1090
source "$VERSIONS_FILE"

ARCH="$(uname -m)"
case "$ARCH" in
  arm64)
    PYTHON_ARCH="aarch64-apple-darwin"
    ;;
  x86_64)
    PYTHON_ARCH="x86_64-apple-darwin"
    ;;
  *)
    echo "Unsupported macOS architecture: $ARCH" >&2
    exit 1
    ;;
esac

PYTHON_TAG="cpython-${PYTHON_VERSION}+${PYTHON_BUILD_RELEASE}-${PYTHON_ARCH}-install_only"
PYTHON_ARCHIVE="${PYTHON_TAG}.tar.gz"
PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PYTHON_BUILD_RELEASE}/${PYTHON_ARCHIVE}"

log() {
  echo "[build-dmg] $*"
}

ensure_dir() {
  mkdir -p "$1"
}

download() {
  local url="$1"
  local dest="$2"
  log "Downloading $url"
  curl -fsSL "$url" -o "$dest"
}

venv_python() {
  local venv_dir="$1"
  if [[ -x "$venv_dir/bin/python3" ]]; then
    echo "$venv_dir/bin/python3"
    return 0
  fi
  if [[ -x "$venv_dir/bin/python" ]]; then
    echo "$venv_dir/bin/python"
    return 0
  fi
  echo "Python interpreter not found in $venv_dir/bin" >&2
  return 1
}

log "Building wheel..."
ensure_dir "$DIST"
if ! python3 -m pip wheel "$ROOT" -w "$DIST"; then
  python3 -m pip install build
  python3 -m build --wheel "$ROOT" -o "$DIST"
fi

PROJECT_WHEEL="$(ls -1 "$DIST"/karaoke_blast-*.whl 2>/dev/null | sort -V | tail -n 1)"
if [[ -z "$PROJECT_WHEEL" ]]; then
  echo "Wheel was not produced in $DIST" >&2
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

log "Preparing staging..."
rm -rf "$STAGING"
ensure_dir "$STAGING"

APP_PATH="$STAGING/$BUILD_APP_BUNDLE"
CONTENTS="$APP_PATH/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"
PYTHON_DIR="$RESOURCES/python"
VENV_DIR="$RESOURCES/venv"
FFMPEG_DIR="$RESOURCES/ffmpeg"

ensure_dir "$MACOS"
ensure_dir "$RESOURCES"

download "$PYTHON_URL" "$TMP/$PYTHON_ARCHIVE"
tar -xzf "$TMP/$PYTHON_ARCHIVE" -C "$TMP"
mv "$TMP/python" "$PYTHON_DIR"

log "Creating virtual environment in app bundle..."
# Create venv after python is in its final path; --copies avoids broken symlinks if moved.
"$PYTHON_DIR/bin/python3" -m venv --copies "$VENV_DIR"
VENV_PY="$(venv_python "$VENV_DIR")"
"$VENV_PY" -m pip install --upgrade pip wheel
"$VENV_PY" -m pip install "$PROJECT_WHEEL"

log "Downloading bundled ffmpeg..."
ensure_dir "$FFMPEG_DIR"
download "$FFMPEG_MACOS_URL" "$TMP/ffmpeg.zip"
ditto -x -k "$TMP/ffmpeg.zip" "$TMP/ffmpeg-extract"
FFMPEG_BIN="$(find "$TMP/ffmpeg-extract" -name ffmpeg -type f | head -n 1)"
if [[ -z "$FFMPEG_BIN" ]]; then
  echo "ffmpeg binary not found in downloaded archive" >&2
  exit 1
fi
cp "$FFMPEG_BIN" "$FFMPEG_DIR/ffmpeg"
chmod +x "$FFMPEG_DIR/ffmpeg"

cp "$SCRIPT_DIR/install-optional-deps.sh" "$RESOURCES/install-optional-deps.sh"
chmod +x "$RESOURCES/install-optional-deps.sh"

cat >"$MACOS/launcher" <<'EOF'
#!/bin/zsh
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
RESOURCES="$APP_DIR/Contents/Resources"
MARKER="$HOME/Library/Application Support/Karaoke Blast/.optional-deps-checked"
VENV_BIN="$RESOURCES/venv/bin"

export PATH="$RESOURCES/ffmpeg:$PATH"

if [[ ! -f "$MARKER" ]]; then
  "$RESOURCES/install-optional-deps.sh" || true
fi

if [[ -x "$VENV_BIN/python3" ]]; then
  exec "$VENV_BIN/python3" -m karaoke_blast "$@"
fi
if [[ -x "$VENV_BIN/python" ]]; then
  exec "$VENV_BIN/python" -m karaoke_blast "$@"
fi
echo "Karaoke Blast: Python runtime not found in $VENV_BIN" >&2
exit 1
EOF
chmod +x "$MACOS/launcher"

APP_VERSION="$(python3 -c "import tomllib; print(tomllib.load(open('$ROOT/pyproject.toml', 'rb'))['project']['version'])")"

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

log "Building app icon..."
"$VENV_PY" "$ROOT/scripts/build_app_icon.py" "$ICON_PNG" "$RESOURCES/AppIcon.icns"

ensure_dir "$DIST"
DMG_PATH="$DIST/${APP_NAME}.dmg"
DMG_STAGING="$TMP/dmg-root"
ensure_dir "$DMG_STAGING"
cp -R "$APP_PATH" "$DMG_STAGING/"
mv "$DMG_STAGING/$BUILD_APP_BUNDLE" "$DMG_STAGING/${APP_NAME}.app"

if [[ -f "$DMG_PATH" ]]; then
  rm -f "$DMG_PATH"
fi

log "Creating DMG..."
hdiutil create -volname "$APP_NAME" -srcfolder "$DMG_STAGING" -ov -format UDZO "$DMG_PATH"

log "Built $DMG_PATH"
