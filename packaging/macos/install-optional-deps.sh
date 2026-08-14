#!/usr/bin/env bash
# Install VLC and ffmpeg only when they are not already available on the system.
set -euo pipefail

RESOURCES="$(cd "$(dirname "$0")" && pwd)"
MARKER="$HOME/Library/Application Support/Karaoke Blast/.optional-deps-checked"

log() {
  echo "[Karaoke Blast] $*"
}

vlc_installed() {
  if [[ -f "/Applications/VLC.app/Contents/MacOS/lib/libvlc.dylib" ]]; then
    return 0
  fi
  for prefix in /opt/homebrew/opt/vlc /usr/local/opt/vlc; do
    if [[ -f "$prefix/lib/libvlc.dylib" || -f "$prefix/lib/libvlc.5.dylib" ]]; then
      return 0
    fi
  done
  return 1
}

ffmpeg_available() {
  if command -v ffmpeg >/dev/null 2>&1; then
    return 0
  fi
  if [[ -x "$RESOURCES/ffmpeg/ffmpeg" ]]; then
    return 0
  fi
  return 1
}

install_vlc() {
  log "VLC not found. Attempting installation..."
  if command -v brew >/dev/null 2>&1; then
    if brew install --cask vlc; then
      if vlc_installed; then
        log "VLC installed via Homebrew."
        return 0
      fi
    fi
  fi
  log "Could not install VLC automatically. Download from https://www.videolan.org/vlc/"
  return 1
}

ensure_bundled_ffmpeg() {
  local bundled="$RESOURCES/ffmpeg/ffmpeg"
  if [[ -x "$bundled" ]]; then
    log "Bundled ffmpeg is available at $bundled"
    return 0
  fi
  log "ffmpeg not found on PATH and no bundled copy exists."
  log "Install with: brew install ffmpeg"
  return 1
}

if vlc_installed; then
  log "VLC is already installed."
else
  install_vlc || true
fi

if ffmpeg_available; then
  log "ffmpeg is available."
else
  ensure_bundled_ffmpeg || true
fi

mkdir -p "$(dirname "$MARKER")"
touch "$MARKER"
log "Optional dependency check complete."
