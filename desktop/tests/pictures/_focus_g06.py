"""Pictures from the views lane's group G06: the focus strip and Material's focus screen. The lead
gathers this fragment into screens_focus.py.

Each one is what an old pixel, position or style-property test read back."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QApplication

from desktop.tests.material_support import pump, show_material
from desktop.tests.pictures.screen import Screen

if TYPE_CHECKING:
    from desktop.native.window import NativeWindow

MATERIAL_SOURCES = ("desktop/native/material", "desktop/native/window.py")


def _material_focus(running: bool, paused: bool = False):
    def prepare(window: NativeWindow) -> object:
        app = QApplication.instance()
        show_material(app, window)
        window._open_focus_screen()
        pump(app)
        focus = window._material_page.bridge.focus
        if running:
            focus.begin()
            pump(app)
        if paused:
            focus.togglePause()
            pump(app)
        return None

    return prepare


SCREENS: list[Screen] = [
    Screen(
        id="focus.material_ready",
        area="focus",
        prepare=_material_focus(running=False),
        checks=(
            "Material's Focus screen before Start. Exactly one filled button is visible: Start. Pause, "
            "Skip and Finish are not shown."
        ),
        sources=MATERIAL_SOURCES,
        styles=("material",),
    ),
    Screen(
        id="focus.material_running",
        area="focus",
        prepare=_material_focus(running=True),
        checks=(
            "Material's Focus screen with a timer running. Exactly one filled button is visible: Pause. "
            "Skip and Finish are not filled. Pause, Skip and Finish keep the same left edge and width "
            "when the timer is paused (compare focus.material_paused)."
        ),
        sources=MATERIAL_SOURCES,
        styles=("material",),
    ),
    Screen(
        id="focus.material_paused",
        area="focus",
        prepare=_material_focus(running=True, paused=True),
        checks=(
            "Material's Focus screen paused: the first button reads Resume and is still the one filled "
            "button, never two filled at once. Pause or Resume, Skip and Finish are at the same left "
            "edge with the same width as in focus.material_running."
        ),
        sources=MATERIAL_SOURCES,
        styles=("material",),
    ),
]
