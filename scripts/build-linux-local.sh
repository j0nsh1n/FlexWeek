#!/usr/bin/env bash
# Build the Linux tarball on this computer, inside an Ubuntu 24.04 container, so it keeps
# the glibc 2.38 promise however new this computer's own system is. Same steps as the
# Developer build workflow; GitHub still publishes developer builds and releases.
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
# Rootless podman cannot pin cores here (no cpuset controller), so --cpus caps CPU time instead.
nice podman run --rm --cpus "$CPUS" --memory "$MEMORY" --security-opt label=disable \
    -e JOBS="$CPUS" -e SMOKE="$SMOKE" -e FLEXWEEK_SILENT=1 \
    -v "$ROOT:/src" -v "$CACHE:/cache" -v "$CACHE/cargo-target:/src/engine/target" -v "$CACHE/cargo-registry:/opt/cargo/registry" \
    -v "$HERE/inside.sh:/inside.sh:ro" \
    "$IMAGE" /inside.sh
echo "Built: $ROOT/dist/release/FlexWeek-Linux-x86_64.tar.gz"
