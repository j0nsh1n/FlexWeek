#!/usr/bin/env bash
# Trim, vendor and check a Nuitka Linux bundle in place. build_linux.sh runs it;
# it can also be rerun on a staging bundle without recompiling.
#
#   desktop/finish_linux_bundle.sh build/linux.XXXXXX/main.dist
#
# The bundle must then pass desktop/check_bundle.py: nothing may need a newer
# glibc than MAX_GLIBC, or a library a normal desktop does not have.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${VENV:-$ROOT/.venv}"
MAX_GLIBC="${MAX_GLIBC:-2.38}"
BUNDLE="${1:?usage: finish_linux_bundle.sh <bundle directory>}"
[[ -x "$BUNDLE/FlexWeek" ]] || { echo "No FlexWeek executable in $BUNDLE" >&2; exit 1; }
command -v readelf >/dev/null || { echo "readelf not found; install binutils" >&2; exit 1; }

# Qt's X11 plugin needs these xcb helpers. Many desktops (Ubuntu and Mint
# among them) do not install them, and Qt then refuses to start on X11.
VENDORED_XCB=(libxcb-cursor.so.0 libxcb-icccm.so.4 libxcb-image.so.0 libxcb-keysyms.so.1
    libxcb-render-util.so.0 libxcb-util.so.1)

system_library() {
    # Reads all of ldconfig's output; stopping early would end the pipe with SIGPIPE.
    ldconfig -p | awk -v soname="$1" '$1 == soname && /x86-64/ && !found { found = $NF } END { print found }'
}

# Qt tool translations (Designer, Linguist...) are never loaded, and Chromium
# only needs its en-US locale pack; removing the whole locale folder instead
# makes WebEngine warn at every start. DevTools resources serve DevTools only.
find "$BUNDLE" -maxdepth 1 -name '*.qm' -delete
find "$BUNDLE/qtwebengine_locales" -name '*.pak' ! -name 'en-US.pak' -delete
rm -f "$BUNDLE/qtwebengine_devtools_resources.pak"

# Upstream COPYING texts live in desktop/linux/licenses, because distro
# packages do not all ship them (Fedora's xcb-util-keysyms has none).
mkdir -p "$BUNDLE/licenses"
for soname in "${VENDORED_XCB[@]}"; do
    source_path="$(system_library "$soname")"
    [[ -n "$source_path" ]] || { echo "$soname is not installed on this build machine" >&2; exit 1; }
    cp -L "$source_path" "$BUNDLE/$soname"
    cp "$ROOT/desktop/linux/licenses/${soname%%.so*}.txt" "$BUNDLE/licenses/"
done

"$VENV/bin/python" -m desktop.check_bundle linux "$BUNDLE" --max-glibc "$MAX_GLIBC"
du -sh "$BUNDLE"
