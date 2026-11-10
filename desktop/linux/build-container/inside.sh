#!/usr/bin/env bash
# Runs inside the build container: the dev-build workflow's build steps on the checkout
# mounted at /src. The venv and the compile caches live under /cache, and the host script
# mounts /cache/cargo-target over engine/target, so the checkout's own .venv and engine/target
# are not touched and the next build is warm.
set -euo pipefail
cd /src
export UV_CACHE_DIR=/cache/uv NUITKA_CACHE_DIR=/cache/nuitka CCACHE_DIR=/cache/ccache \
       VENV=/cache/venv VIRTUAL_ENV=/cache/venv \
       CARGO_BUILD_JOBS="$JOBS" FLEXWEEK_BUILD_JOBS="$JOBS"
step() { local name="$1" start; shift; start=$(date +%s); echo "== $name"; "$@"; echo "== $name done in $(( $(date +%s) - start ))s"; }

python="$(command -v python3.14)"
# A fresh venv whenever the requirements or the Python change, so a package dropped from the
# requirements is gone here too, as in the workflow's fresh venv.
venv() {
    local want have=""
    want="$( (cat requirements.txt requirements-desktop.txt requirements-dev.txt; "$python" -VV) | sha256sum | cut -c1-16)"
    [ -f "$VENV/.requirements" ] && have="$(cat "$VENV/.requirements")"
    if [ "$want" != "$have" ] || [ ! -x "$VENV/bin/python" ]; then
        rm -rf "$VENV" && uv venv -q -p "$python" "$VENV"
        uv pip install -q -p "$VENV/bin/python" -r requirements.txt -r requirements-desktop.txt -r requirements-dev.txt
        echo "$want" > "$VENV/.requirements"
    fi
}
step rust rustup toolchain install stable --profile minimal --no-self-update
step venv venv
step engine "$VENV/bin/python" -m maturin develop --release --manifest-path engine/py/Cargo.toml
# build_linux.sh keeps each run's Nuitka staging in build/linux.*; a run here needs none of the old ones.
rm -rf dist/FlexWeek dist/release build/linux.*
step bundle ./desktop/build_linux.sh
rm -rf build/linux.*
step package ./desktop/package_linux.sh dist/FlexWeek dist/release

if [ "${SMOKE:-0}" = 1 ]; then
    # The workflow's smoke steps, on the tarball a user gets.
    smoke() {
        rm -rf dist/stage && mkdir dist/stage
        tar -xzf dist/release/FlexWeek-Linux-x86_64.tar.gz -C dist/stage
        if find dist/stage/FlexWeek dist/FlexWeek -name '*WebEngineCore*' | grep -q .; then
            echo "Native package must not ship WebEngine" >&2
            return 1
        fi
        QT_QPA_PLATFORM=offscreen LD_LIBRARY_PATH="" \
            xvfb-run -a -s "-screen 0 1280x800x24" dist/stage/FlexWeek/FlexWeek --smoke-test dist/packaged-smoke.json
        "$python" -c 'import json,sys; r=json.load(open("dist/packaged-smoke.json")); print(r); sys.exit(0 if r.get("ok") and r.get("stage") == "week shown after setup Solve" else 1)'
        "$python" desktop/smoke_mcp.py dist/stage/FlexWeek/FlexWeek --timeout 60
        if grep -q "/" dist/release/FlexWeek-Linux-x86_64.tar.gz.sha256; then
            echo "The checksum file names a directory, not just the file." >&2
            return 1
        fi
        (cd dist/release && sha256sum -c FlexWeek-Linux-x86_64.tar.gz.sha256)
    }
    step smoke smoke
fi
