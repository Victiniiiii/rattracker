#!/usr/bin/env bash
# Build a DMG from a Nuitka .app bundle.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="${1:-1.1.0}"
APP="${2:-$ROOT/build/app_qt.app}"
OUT_DIR="${3:-$ROOT/dist}"

test -d "$APP" || { echo "Missing app bundle: $APP"; exit 1; }
mkdir -p "$OUT_DIR"
OUT="$OUT_DIR/rattracker_${VERSION}_$(uname -m).dmg"
rm -f "$OUT"
hdiutil create -volname "Morris Water Maze Analysis" -srcfolder "$APP" \
  -ov -format UDZO "$OUT"
echo "Built $OUT"
