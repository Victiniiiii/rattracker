#!/usr/bin/env bash
# Build an AppImage from a Nuitka standalone directory.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="${1:-1.1.0}"
STANDALONE="${2:-$ROOT/build/app_qt.dist}"
OUT_DIR="${3:-$ROOT/dist}"
ARCH_RAW="$(uname -m)"
case "$ARCH_RAW" in
  x86_64) APPIMAGE_ARCH=x86_64 ;;
  aarch64|arm64) APPIMAGE_ARCH=aarch64 ;;
  *) echo "Unsupported architecture: $ARCH_RAW"; exit 1 ;;
esac

test -x "$STANDALONE/rattracker" || { echo "Missing $STANDALONE/rattracker"; exit 1; }
mkdir -p "$OUT_DIR"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
APPDIR="$WORK/RatTracker.AppDir"
mkdir -p "$APPDIR/usr/bin"
cp -a "$STANDALONE/." "$APPDIR/usr/bin/"
install -m 0644 "$ROOT/appicon.png" "$APPDIR/rattracker.png"
install -m 0644 "$ROOT/appicon.png" "$APPDIR/.DirIcon"

cat > "$APPDIR/rattracker.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Morris Water Maze Analysis
Comment=Track a rat in a water maze video
Exec=rattracker
Icon=rattracker
Terminal=false
Categories=Science;Video;Education;
DESKTOP

cat > "$APPDIR/AppRun" <<'SH'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/rattracker" "$@"
SH
chmod 0755 "$APPDIR/AppRun"

TOOL="${APPIMAGETOOL:-$HOME/.cache/rattracker/appimagetool-$APPIMAGE_ARCH.AppImage}"
if [ ! -x "$TOOL" ]; then
  mkdir -p "$(dirname "$TOOL")"
  URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${APPIMAGE_ARCH}.AppImage"
  echo "Downloading $URL"
  curl -fL --retry 3 -o "$TOOL" "$URL"
  chmod +x "$TOOL"
fi

OUT="$OUT_DIR/rattracker_${VERSION}_${APPIMAGE_ARCH}.AppImage"
rm -f "$OUT"
ARCH="$APPIMAGE_ARCH" "$TOOL" --appimage-extract-and-run "$APPDIR" "$OUT"
echo "Built $OUT"
