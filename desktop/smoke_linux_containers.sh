#!/usr/bin/env bash
# Start a packaged FlexWeek on fresh Linux desktop installs, one container each.
#
#   desktop/smoke_linux_containers.sh dist/release/FlexWeek-Linux-x86_64.tar.gz [distro...]
#
# Each image is a stock distro plus its desktop metapackage and a virtual X
# server, nothing FlexWeek-specific, so a missing library shows up here the way
# it would for a student. The app runs as an ordinary user with an empty home
# and must reach its first screen through `FlexWeek --smoke-test`.
# Needs podman (or docker via ENGINE=docker) and network access the first time.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENGINE="${ENGINE:-podman}"
ARCHIVE="$(readlink -f "${1:?usage: smoke_linux_containers.sh <FlexWeek-Linux tar.gz> [distro...]}")"
shift
DISTROS=("${@:-ubuntu-24.04 debian-13}")
read -r -a DISTROS <<< "${DISTROS[*]}"
RESULTS="$ROOT/build/smoke"
mkdir -p "$RESULTS"

image_recipe() {
    case "$1" in
        ubuntu-24.04) cat <<'EOF'
FROM docker.io/library/ubuntu:24.04
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ubuntu-desktop-minimal xvfb xauth && rm -rf /var/lib/apt/lists/*
RUN useradd -m student
EOF
        ;;
        debian-13) cat <<'EOF'
FROM docker.io/library/debian:trixie
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    task-xfce-desktop xvfb xauth && rm -rf /var/lib/apt/lists/*
RUN useradd -m student
EOF
        ;;
        debian-12) cat <<'EOF'
FROM docker.io/library/debian:bookworm
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    xvfb xauth && rm -rf /var/lib/apt/lists/*
RUN useradd -m student
EOF
        ;;
        *) echo "Unknown distro $1" >&2; return 1 ;;
    esac
}

status=0
for distro in "${DISTROS[@]}"; do
    tag="localhost/flexweek-smoke:$distro"
    if ! "$ENGINE" image inspect "$tag" >/dev/null 2>&1; then
        image_recipe "$distro" | "$ENGINE" build -t "$tag" -f - "$RESULTS" >/dev/null
    fi
    out="$RESULTS/$distro"
    rm -rf "$out"
    mkdir -p "$out"
    chmod 777 "$out"
    echo "== $distro"
    if "$ENGINE" run --rm --user student -v "$ARCHIVE:/archive.tar.gz:ro,Z" -v "$out:/out:Z" "$tag" \
        bash -c 'cd ~ && tar -xzf /archive.tar.gz && (ldd FlexWeek/FlexWeek | grep "not found" > /out/missing.txt || true);
                 timeout 150 xvfb-run -a -s "-screen 0 1280x800x24" FlexWeek/FlexWeek --smoke-test /out/report.json \
                 > /out/app.log 2>&1'; then
        echo "PASS: $(tr -d '\n ' < "$out/report.json")"
    else
        status=1
        echo "FAIL: see $out"
        [[ -s "$out/missing.txt" ]] && cat "$out/missing.txt"
        [[ -f "$out/report.json" ]] && cat "$out/report.json"
        grep -v -i "vulkan\|dbus" "$out/app.log" | tail -15 || true
    fi
done
exit "$status"
