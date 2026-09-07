#!/usr/bin/env bash
# Build the FlexWeek Linux desktop shell (onedir standalone).
#
# Produces dist/FlexWeek/FlexWeek — runs without a Python install and without a
# separate server: the FastAPI backend is bundled and started in-process.
# frontend/ ships as data because backend/app.py serves it from <bundle>/frontend.
# Qt WebEngine cannot be statically linked, so the Chromium libraries ship
# alongside the binary; --onefile is deliberately not used (see DESKTOP.md).
#
# Nuitka is what pyside6-deploy shells out to. It is driven directly here
# because pyside6-deploy rewrites its own .spec with absolute paths on every
# run, which does not survive being committed to a repository.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${VENV:-$ROOT/.venv}"
OUT="$ROOT/dist"

# Nuitka looks for patchelf on PATH, not in site-packages.
export PATH="$VENV/bin:$PATH"
export PYTHONPATH="$ROOT"

command -v patchelf >/dev/null || { echo "patchelf not found; pip install -r requirements-desktop.txt" >&2; exit 1; }

rm -rf "$OUT" "$ROOT/build"
"$VENV/bin/python" -m nuitka "$ROOT/desktop/main.py" \
    --standalone \
    --follow-imports \
    --enable-plugin=pyside6 \
    --include-package=desktop \
    --include-package=backend \
    --include-data-dir="$ROOT/frontend"=frontend \
    --noinclude-data-files='frontend/tests/*' \
    --output-filename=FlexWeek \
    --output-dir="$ROOT/build" \
    --linux-icon="$ROOT/frontend/logo.png" \
    --noinclude-dlls='*.cpp.o' \
    --noinclude-dlls='*.qsb' \
    --include-qt-plugins=networkinformation,platforminputcontexts,position,qmllint,qmltooling,vectorimageformats \
    --assume-yes-for-downloads

mkdir -p "$OUT"
mv "$ROOT/build/main.dist" "$OUT/FlexWeek"
rm -rf "$ROOT/build"

echo
echo "Built: $OUT/FlexWeek/FlexWeek"
du -sh "$OUT/FlexWeek"
