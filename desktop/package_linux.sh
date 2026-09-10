#!/usr/bin/env bash
# Turn a finished Linux bundle into the release download.
#
#   desktop/package_linux.sh [bundle] [output directory]
#
# Produces FlexWeek-Linux-x86_64.tar.gz holding one FlexWeek/ folder with the
# app, README.txt, flexweek.desktop, flexweek.png, install-menu-entry.sh and
# LICENSE.txt, plus FlexWeek-Linux-x86_64.tar.gz.sha256. A tar.gz keeps the
# executable bit that a zip loses. Set FLEXWEEK_WEB_URL to point Chromebook
# users at the hosted web version; without it the README says none is online.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE="$(readlink -f "${1:-$ROOT/dist/FlexWeek}")"
OUTPUT="${2:-$ROOT/dist/release}"
NAME="FlexWeek-Linux-x86_64.tar.gz"

[[ -x "$BUNDLE/FlexWeek" ]] || { echo "No FlexWeek executable in $BUNDLE" >&2; exit 1; }
mkdir -p "$OUTPUT"
[[ ! -e "$OUTPUT/$NAME" ]] || { echo "$OUTPUT/$NAME already exists; move it first" >&2; exit 1; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cp -a "$BUNDLE" "$WORK/FlexWeek"
cp "$ROOT/desktop/linux/flexweek.desktop" "$ROOT/desktop/linux/install-menu-entry.sh" "$WORK/FlexWeek/"
cp "$ROOT/frontend/logo.png" "$WORK/FlexWeek/flexweek.png"
cp "$ROOT/LICENSE" "$WORK/FlexWeek/LICENSE.txt"
PYTHONPATH="$ROOT" python3 -m desktop.readme "$ROOT/desktop/linux/README.txt" "$WORK/FlexWeek/README.txt"
chmod +x "$WORK/FlexWeek/FlexWeek" "$WORK/FlexWeek/install-menu-entry.sh"

tar -C "$WORK" --owner=0 --group=0 --numeric-owner -czf "$OUTPUT/$NAME" FlexWeek
(cd "$OUTPUT" && sha256sum "$NAME" > "$NAME.sha256")
echo "Packaged: $OUTPUT/$NAME ($(du -h "$OUTPUT/$NAME" | cut -f1))"
