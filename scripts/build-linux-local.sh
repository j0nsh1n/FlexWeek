#!/usr/bin/env bash
# Build the Linux tarball on this computer, inside an Ubuntu 24.04 container, so it keeps
# the glibc 2.38 promise however new this computer's own system is. The Developer build
# workflow's stamp, build and smoke steps; GitHub still publishes developer builds and
# releases. Replaces dist/FlexWeek and dist/release.
#
#   scripts/build-linux-local.sh            # -> dist/release/FlexWeek-Linux-x86_64.tar.gz
#   scripts/build-linux-local.sh --smoke    # and run the workflow's smoke tests on it
#
# Needs podman. Caps: BUILD_CPUS (default 8) cores' worth of CPU, BUILD_MEMORY (default 10g).
# Compile caches stay in BUILD_CACHE (default ~/.flexweek-ui-harness/build-cache) between builds.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HERE="$ROOT/desktop/linux/build-container"
CPUS="${BUILD_CPUS:-8}"
MEMORY="${BUILD_MEMORY:-10g}"
CACHE="${BUILD_CACHE:-$HOME/.flexweek-ui-harness/build-cache}"
SMOKE=0
for arg in "$@"; do
    case "$arg" in
        --smoke) SMOKE=1 ;;
        *) echo "usage: $0 [--smoke]" >&2; exit 2 ;;
    esac
done

command -v podman >/dev/null || { echo "podman is not installed." >&2; exit 1; }

# The image is named after its recipe, so editing the Containerfile builds a new one.
IMAGE="localhost/flexweek-linux-build:$(sha256sum "$HERE/Containerfile" | cut -c1-12)"
if ! podman image exists "$IMAGE"; then
    echo "Building the build image $IMAGE (once per Containerfile change)..."
    nice podman build -t "$IMAGE" -f "$HERE/Containerfile" "$HERE"
fi

mkdir -p "$CACHE/uv" "$CACHE/nuitka" "$CACHE/ccache" "$CACHE/cargo-registry" "$CACHE/cargo-target"

# The workflow's developer version and channel stamp, on the checkout's own version.py, which is
# put back however the build ends (the copy is kept here, outside the container, so a killed
# container cannot lose it). A stamp already there means an earlier run was killed before it
# could put the file back; saving that as the original would keep the stamp for good.
VERSION_FILE="$ROOT/desktop/native/version.py"
SAVED="$CACHE/version.py.saved"
if grep -q '^CHANNEL = "dev"' "$VERSION_FILE"; then
    echo "$VERSION_FILE already says CHANNEL = \"dev\": an earlier run was stopped before putting it back." >&2
    echo "Put it back (git checkout -- desktop/native/version.py) and run again." >&2
    exit 1
fi
cp -p "$VERSION_FILE" "$SAVED"
NAME="flexweek-linux-build-$$"
trap 'cp -p "$SAVED" "$VERSION_FILE"' EXIT
# Stopped by Ctrl+C or a kill: stop the container too, then the EXIT trap puts version.py back.
trap 'podman stop -t 10 "$NAME" >/dev/null 2>&1; exit 130' INT TERM HUP
BASE="$(sed -n 's/^VERSION = "\(.*\)"/\1/p' "$VERSION_FILE")"
[ -n "$BASE" ] || { echo "Could not read the version from $VERSION_FILE" >&2; exit 1; }
DEVVERSION="$BASE.$(date -u +%Y%m%d%H%M)"
sed -i "s/^VERSION = \".*\"/VERSION = \"$DEVVERSION\"/" "$VERSION_FILE"
sed -i 's/^CHANNEL = "release"/CHANNEL = "dev"/' "$VERSION_FILE"
grep -q "^VERSION = \"$DEVVERSION\"" "$VERSION_FILE" && grep -q '^CHANNEL = "dev"' "$VERSION_FILE"
echo "Developer version $DEVVERSION"
# Rootless podman cannot pin cores here (no cpuset controller), so --cpus caps CPU time instead.
nice podman run --rm --init --name "$NAME" --cpus "$CPUS" --memory "$MEMORY" --memory-swap "$MEMORY" --security-opt label=disable \
    -e JOBS="$CPUS" -e SMOKE="$SMOKE" -e FLEXWEEK_SILENT=1 \
    -v "$ROOT:/src" -v "$CACHE:/cache" -v "$CACHE/cargo-target:/src/engine/target" -v "$CACHE/cargo-registry:/opt/cargo/registry" \
    -v "$HERE/inside.sh:/inside.sh:ro" \
    "$IMAGE" /inside.sh &
# Waiting in the background lets a signal reach the traps at once instead of after the build.
wait $!
echo "Built: $ROOT/dist/release/FlexWeek-Linux-x86_64.tar.gz (developer version $DEVVERSION)"
