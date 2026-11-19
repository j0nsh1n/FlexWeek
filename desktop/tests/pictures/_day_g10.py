"""Day pictures that came out of test_layouts_window.py (the lead folds this fragment into
screens_day.py)."""

from __future__ import annotations

from PySide6.QtWidgets import QAbstractButton

from desktop.native.window import NativeWindow
from desktop.tests.day.support_layouts_window import school_week, still
from desktop.tests.pictures.screen import Screen


def _todays_app_day(window: NativeWindow) -> object:
    school_week(window)
    window._layout = {"main": "classic", "day": "one", "options": {}}
    window.findChild(QAbstractButton, "viewDay").click()
    still(window)
    return window.day_view


SCREENS: list[Screen] = [
    Screen(
        id="day.day_view_buttons_keep_their_width",
        area="day",
        prepare=_todays_app_day,
        checks=(
            "Today's app Day view: no button spreads across the window like a banner. Each visible "
            "button is its own natural width, at most 8 px wider than its size hint (a full-width button "
            "was seen on the Day view)."
        ),
        sources=("desktop/native/hours/classic.py", "desktop/native/window.py"),
    ),
]
