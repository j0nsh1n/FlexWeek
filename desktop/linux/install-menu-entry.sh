#!/bin/sh
# Add FlexWeek to your app menu, for your user only. No password needed.
#   ./install-menu-entry.sh              add it
#   ./install-menu-entry.sh --uninstall  remove it
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
ENTRY="$DATA/applications/flexweek.desktop"
ICON="$DATA/icons/hicolor/256x256/apps/flexweek.png"

refresh_menu() {
    update-desktop-database "$DATA/applications" 2>/dev/null || true
    kbuildsycoca6 2>/dev/null || kbuildsycoca5 2>/dev/null || true
}

if [ "${1:-}" = "--uninstall" ]; then
    rm -f "$ENTRY" "$ICON"
    refresh_menu
    echo "Removed FlexWeek from your app menu. Your weeks are still saved."
    exit 0
fi

# A desktop entry's Exec line cannot safely carry these characters.
case "$HERE" in
    *[\"\`\$\\%]*)
        echo "Move the FlexWeek folder to a path without \" \` \$ \\ or % and run this again." >&2
        exit 1
        ;;
esac

mkdir -p "$(dirname "$ENTRY")" "$(dirname "$ICON")"
cp "$HERE/flexweek.png" "$ICON"
sed -e '/^#/d' -e "s|^Exec=.*|Exec=\"$HERE/FlexWeek\"|" "$HERE/flexweek.desktop" > "$ENTRY"
chmod 644 "$ENTRY"
refresh_menu
echo "FlexWeek is now in your app menu."
echo "Keep this folder at $HERE. The menu entry starts FlexWeek from here."
