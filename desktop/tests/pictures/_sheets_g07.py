"""The toast as a picture. The aggregator collects SCREENS."""

from __future__ import annotations

from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen


def toast_corner(window: NativeWindow) -> object:
    window.toast.show_message("Test message", "Undo")
    window.toast.reposition()
    return None


SCREENS: list[Screen] = [
    Screen(
        id="sheets.toast_corner",
        area="sheets",
        prepare=toast_corner,
        checks=(
            "The toast card is anchored to the bottom right of the page, wholly inside the window: its "
            "right edge no further than the window's, its left edge past the middle, its top in the "
            "lower half."
        ),
        sources=("desktop/native/widgets.py", "desktop/native/window.py"),
    ),
]
