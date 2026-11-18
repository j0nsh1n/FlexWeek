"""Screens of the sync area: the sync status dot."""

from __future__ import annotations

from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.window_support import still

SOURCES = ("desktop/native/devices.py", "desktop/native/settings.py")


def sync_dot_with_a_problem(window: NativeWindow) -> object:
    window.sync_dot.show_state("problem")
    still(window)
    return window.sync_dot.parentWidget()


SCREENS: list[Screen] = [
    Screen(
        id="sync.status_dot_problem",
        area="sync",
        prepare=sync_dot_with_a_problem,
        checks=(
            "The 10 px sync dot in the status strip is filled with the look's error colour when sync "
            "has a problem, so it reads as a problem in every look, light and dark, and stays visible "
            "against the strip behind it. It is round and is not cut off."
        ),
        sources=SOURCES,
    ),
]
