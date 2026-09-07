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
OUT="${FLEXWEEK_BUILD_OUTPUT:-$ROOT/dist/FlexWeek}"

# Nuitka looks for patchelf on PATH, not in site-packages.
export PATH="$VENV/bin:$PATH"
export PYTHONPATH="$ROOT"

command -v patchelf >/dev/null || { echo "patchelf not found; pip install -r requirements-desktop.txt" >&2; exit 1; }

mkdir -p "$ROOT/build"
STAGING="$(mktemp -d "$ROOT/build/linux.XXXXXX")"
trap 'echo "Build staging retained at $STAGING" >&2' ERR
"$VENV/bin/python" -m nuitka "$ROOT/desktop/main.py" \
    --standalone \
    --follow-imports \
    --enable-plugin=pyside6 \
    --include-package=desktop \
    --include-package=backend \
    --nofollow-import-to=desktop.tests,backend.tests \
    --include-data-dir="$ROOT/frontend"=frontend \
    --noinclude-data-files='frontend/tests/*' \
    --output-filename=FlexWeek \
    --output-dir="$STAGING" \
    --linux-icon="$ROOT/frontend/logo.png" \
    --noinclude-dlls='*.cpp.o' \
    --noinclude-dlls='*.qsb' \
    --include-qt-plugins=networkinformation,platforminputcontexts,position,qmllint,qmltooling,vectorimageformats \
    --jobs="${FLEXWEEK_BUILD_JOBS:-4}"

mkdir -p "$(dirname "$OUT")"
BACKUP=""
if [[ -e "$OUT" ]]; then
    BACKUP="$OUT.previous.$(date +%Y%m%d-%H%M%S)"
    [[ ! -e "$BACKUP" ]] || { echo "Backup already exists: $BACKUP" >&2; exit 1; }
    mv "$OUT" "$BACKUP"
fi
if ! mv "$STAGING/main.dist" "$OUT"; then
    [[ -z "$BACKUP" ]] || mv "$BACKUP" "$OUT"
    exit 1
fi

echo "Built: $OUT/FlexWeek"
[[ -z "$BACKUP" ]] || echo "Previous build preserved: $BACKUP"
echo "Build intermediates retained: $STAGING"
du -sh "$OUT"
