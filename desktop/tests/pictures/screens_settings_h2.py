"""Settings picture for Material's colour tokens (R3.4 forms lane, chunk H2). The check is what the old
code tests asserted about colours and contrast, with their numbers. The Widgets looks, controls, toast
and menu screens went with the Widgets painting."""

from __future__ import annotations

from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.window_support import still


def material_tokens(window: NativeWindow) -> object:
    window.show()
    still(window)
    return None


SCREENS: list[Screen] = [
    Screen(
        id="settings.material_tokens",
        area="settings",
        prepare=material_tokens,
        checks=(
            "In Material 3: status words (Done, Due soon, Overdue) in the light mode reach 4.5 to 1 "
            "on white, "
            "and each status word reaches 4.5 to 1 on its own tint; every class bar reaches 3 to 1 on the "
            "card; every block's ink reaches 4.5 to 1 on its fill and is never white or the class colour; "
            "the focus ring reaches 3 to 1 on the card and on the page, in light and dark."
        ),
        sources=("desktop/native/material",),
        main=True,
        styles=("material",),
    ),
]
