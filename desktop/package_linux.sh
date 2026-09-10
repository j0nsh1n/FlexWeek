#!/usr/bin/env bash
# Turn a finished Linux bundle into the release download.
#
#   desktop/package_linux.sh [bundle] [output directory]
#
# Produces FlexWeek-Linux-x86_64.tar.gz holding one FlexWeek/ folder whose top
# level is only the things a human touches — the FlexWeek launcher, README.txt,
# flexweek.desktop, flexweek.png, install-menu-entry.sh and LICENSE.txt — with
# the compiled payload (Qt, Python, frontend) inside app/, so the executable
# stands out instead of drowning in library files. The launcher keeps the name
# FlexWeek, so the README's "./FlexWeek" and the menu installer's Exec= line
# stay true. Plus FlexWeek-Linux-x86_64.tar.gz.sha256. A tar.gz keeps the
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
TOP="$WORK/FlexWeek"
mkdir -p "$TOP"

# The compiled payload moves into app/ untouched; everything at the top level
# is a file a human reads, clicks or copies.
cp -a "$BUNDLE" "$TOP/app"
cat > "$TOP/FlexWeek" << 'EOF'
#!/bin/sh
HERE="$(cd "$(dirname "$0")" && pwd)"
exec "$HERE/app/FlexWeek" "$@"
EOF
cp "$ROOT/desktop/linux/flexweek.desktop" "$ROOT/desktop/linux/install-menu-entry.sh" "$TOP/"
cp "$ROOT/frontend/logo.png" "$TOP/flexweek.png"
cp "$ROOT/LICENSE" "$TOP/LICENSE.txt"
PYTHONPATH="$ROOT" python3 -m desktop.readme "$ROOT/desktop/linux/README.txt" "$TOP/README.txt"
chmod +x "$TOP/FlexWeek" "$TOP/install-menu-entry.sh" "$TOP/app/FlexWeek"

# The launcher must reach the payload it promises to start.
[[ -x "$TOP/app/FlexWeek" ]] || { echo "Staged app/FlexWeek is missing or not executable" >&2; exit 1; }
sh -n "$TOP/FlexWeek"

tar -C "$WORK" --owner=0 --group=0 --numeric-owner -czf "$OUTPUT/$NAME" FlexWeek
(cd "$OUTPUT" && sha256sum "$NAME" > "$NAME.sha256")
echo "Packaged: $OUTPUT/$NAME ($(du -h "$OUTPUT/$NAME" | cut -f1))"
