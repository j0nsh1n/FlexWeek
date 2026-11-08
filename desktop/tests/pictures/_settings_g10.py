"""Settings pictures that came out of test_layouts_window.py (the lead folds this fragment into
screens_settings.py)."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QCheckBox

from desktop.native.settings import SettingsPage
from desktop.native.window import NativeWindow
from desktop.tests.day.support_layouts_window import open_settings, school_week, still
from desktop.tests.pictures.screen import Screen


def _page_fills_the_window(window: NativeWindow) -> object:
    school_week(window)
    open_settings(window)
    for _ in range(30):
        QApplication.processEvents()
    still(window)
    return None


def _every_level_open(window: NativeWindow) -> object:
    busiest = {
        "main": "timeline",
        "day": "dial",
        "options": {"timeline": {"finished": "hide"}, "dial": {"list": "hide"}},
    }
    dialog = SettingsPage(None, {}, {}, {}, busiest)
    dialog.show()
    QApplication.processEvents()
    return dialog


def _sections_fit_the_width(window: NativeWindow) -> object:
    school_week(window)
    window.resize(800, 700)
    page = open_settings(window)
    for name in ("prefFineTune", "layoutMainMore", "layoutDayMore"):
        box = page.findChild(QCheckBox, name)
        if box is not None:
            box.setChecked(True)
    QApplication.processEvents()
    still(window)
    return None


SCREENS: list[Screen] = [
    Screen(
        id="settings.page_fills_the_window",
        area="settings",
        prepare=_page_fills_the_window,
        checks=(
            "Settings opened by the gear fills the window in place of the week: the page is as wide as "
            "the window's stack and as tall as it, with Done in view (not below the bottom edge), at "
            "1024 x 768 and 1280 x 800, Light and Dark frost."
        ),
        sources=("desktop/native/settings.py", "desktop/native/window.py"),
        main=True,
    ),
    Screen(
        id="settings.layout_choices_fit_a_laptop",
        area="settings",
        prepare=_every_level_open,
        checks=(
            "Settings with every level open (Timeline with Finished hidden, Day dial with its list "
            "hidden, both Fine-tune boxes ticked) is at most 1366 x 768 in size and in its size hint, "
            "so it fits a laptop."
        ),
        sources=("desktop/native/settings.py",),
    ),
    Screen(
        id="settings.sections_fit_the_width",
        area="settings",
        prepare=_sections_fit_the_width,
        checks=(
            "At the narrowest window (800 x 700) with every Fine-tune box ticked, Settings scrolls down, "
            "never sideways: in each section (click each name in the list on the left in turn) nothing "
            "is cut off at the right (every dropdown keeps its arrow, the layout blurbs do not stop "
            "mid-word) and the list's longest name, \"Appearance & layout\", is whole. Look at "
            "Normal and Large text and at every Main view and Day screen choice."
        ),
        sources=("desktop/native/settings.py",),
    ),
]
