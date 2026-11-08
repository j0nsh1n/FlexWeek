"""Screens for the checks that left desktop/tests/e2e: how the sign-in card draws its keep box."""

from __future__ import annotations

from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import still

SOURCES = ("desktop/native/window.py", "desktop/native/look.py")


def _sign_in_card(box_ticked: bool):
    def prepare(window: NativeWindow) -> object:
        window.session.logout()
        wait_until(
            None,
            lambda: window._stack.currentWidget().objectName() == "authPage" and not window.session.busy,
            what="the sign-in card after signing out",
        )
        window.keep_signed_in.setChecked(box_ticked)
        still(window)
        return window._auth_card

    return prepare


SCREENS: list[Screen] = [
    Screen(
        id="planner.sign_in_keep_box_unticked",
        area="planner",
        prepare=_sign_in_card(False),
        checks=(
            "The 'Keep me signed in on this computer' box, unticked, can be seen on the white card: an "
            "outline is drawn at the box's left end, clearly darker than the card (the old check counted "
            "at least 20 pixels in the box's first 22 columns that differ from the card's lightness by "
            "more than 60). It must not be the faint Fusion line that vanished on the card on the KDE "
            "desktop."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="planner.sign_in_keep_box_ticked",
        area="planner",
        prepare=_sign_in_card(True),
        checks=(
            "The same box, ticked, is filled: visibly more of it is marked than when unticked (the old "
            "check required more contrasting pixels ticked than unticked), and the tick or fill reads "
            "against the card's colour, not only against the label's."
        ),
        sources=SOURCES,
    ),
]
