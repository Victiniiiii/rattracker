#!/usr/bin/env bash
# Build a .deb from a Nuitka standalone directory.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="${1:-$(cat "$ROOT/VERSION")}"
STANDALONE="${2:-$ROOT/build/app_qt.dist}"
OUT_DIR="${3:-$ROOT/dist}"
ARCH="$(dpkg --print-architecture)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

test -x "$STANDALONE/rattracker" || { echo "Missing $STANDALONE/rattracker"; exit 1; }
mkdir -p "$OUT_DIR"

PKG="$WORK/rattracker_${VERSION}_${ARCH}"
mkdir -p "$PKG/DEBIAN" "$PKG/usr/lib/rattracker" "$PKG/usr/bin" \
         "$PKG/usr/share/applications" "$PKG/usr/share/icons/hicolor/256x256/apps"
cp -a "$STANDALONE/." "$PKG/usr/lib/rattracker/"
install -m 0644 "$ROOT/appicon.png" "$PKG/usr/share/icons/hicolor/256x256/apps/rattracker.png"

cat > "$PKG/usr/bin/rattracker" <<'SH'
#!/bin/sh
exec /usr/lib/rattracker/rattracker "$@"
SH
chmod 0755 "$PKG/usr/bin/rattracker"

cat > "$PKG/usr/share/applications/rattracker.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Rat Tracker
Comment=Track a rat in a video
Exec=rattracker
Icon=rattracker
Terminal=false
Categories=Science;Video;Education;
DESKTOP

cat > "$PKG/DEBIAN/control" <<CONTROL
Package: rattracker
Version: ${VERSION}
Section: science
Priority: optional
Architecture: ${ARCH}
Maintainer: RatTracker
Depends: libc6, libstdc++6, libgl1, libegl1, libxkbcommon0, libxcb-cursor0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-randr0, libxcb-render-util0, libxcb-shape0, libxcb-xinerama0, libdbus-1-3, libfontconfig1
Description: Rat tracking desktop application
 Desktop application that tracks a rat in a video and writes
 coordinates, summary, tracemap, heatmap and an annotated video next to it.
CONTROL

dpkg-deb --root-owner-group --build "$PKG" "$OUT_DIR/rattracker_${VERSION}_${ARCH}.deb"
echo "Built $OUT_DIR/rattracker_${VERSION}_${ARCH}.deb"
