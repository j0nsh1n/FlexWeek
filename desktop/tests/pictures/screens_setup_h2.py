"""Setup pictures from the forms lane's chunk H2: the Style carousel beside its stepper rail."""

from __future__ import annotations

from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.settings.support_pictures import pump
from desktop.tests.window_support import still


def style_carousel(window: NativeWindow) -> object:
    window.resize(1280, 800)
    window.show()
    window._run_setup_again()
    page = window.setup_page
    pump(lambda: page.carousel.isVisible())
    still(window)
    return page


SCREENS: list[Screen] = [
    Screen(
        id="setup.style_carousel_beside_rail",
        area="setup",
        prepare=style_carousel,
        checks=(
            "Setup's Style carousel at 1280 by 800: the stepper rail on the left is visible and clean, "
            "starting at x of 0 or more with a width above 0; the carousel's middle slide is visible and "
            "styled, its neighbour cards show their peek margins; the rail and the carousel do not overlap."
        ),
        sources=("desktop/native/setup.py", "desktop/native/layouts"),
        styles=("widgets",),
    ),
]
