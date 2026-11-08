"""Account pictures that came out of test_layouts_window.py (the lead folds this fragment into
screens_account.py)."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.look import sanitize_look
from desktop.native.window import NativeWindow
from desktop.tests.day.support_layouts_window import school_week, still
from desktop.tests.pictures.screen import Screen


def _sign_in_after_a_laptop_sized_signed_in_window(window: NativeWindow) -> object:
    school_week(window)
    knobs = {**window._look.get("knobs", {}), "text": "large"}
    window._look = sanitize_look({**window._look, "knobs": knobs})
    window._apply_appearance()
    window._day_mode = False
    window._layout = {"main": "retro", "day": "dial", "options": {}}
    window._on_week()
    QApplication.processEvents()
    window._show_page("authPage")
    QApplication.processEvents()
    still(window)
    return None


SCREENS: list[Screen] = [
    Screen(
        id="account.sign_in_card_is_held_at_its_tallest_page",
        area="account",
        prepare=_sign_in_after_a_laptop_sized_signed_in_window,
        checks=(
            "Back on the sign-in page after being signed in on Retro at Large text, the card is held at "
            "the height of its tallest page (Create or Reset): the holder's minimum height is more than "
            "the card's own size hint, so nothing jumps between the card's pages. While signed in and "
            "the page is hidden the card must not be held (it made Retro's window 782 px tall at Large "
            "text, past a 768 px laptop)."
        ),
        sources=("desktop/native/window.py",),
    ),
]
