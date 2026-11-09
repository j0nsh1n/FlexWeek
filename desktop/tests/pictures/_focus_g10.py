"""Focus pictures that came out of test_layouts_window.py (the lead folds this fragment into
screens_focus.py)."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.day.support_layouts_window import school_week, still, wait_until
from desktop.tests.pictures.screen import Screen


def _running_in_bento(window: NativeWindow) -> object:
    school_week(window)
    window._layout = {"main": "bento", "day": "one", "options": {}}
    window._on_week()
    block = next(b for b in window.session.blocks if b.get("assignment_id"))
    window.session.start_focus(block["id"], 3)
    wait_until(QApplication.instance(), lambda: window.session.focus is not None)
    QApplication.processEvents()
    still(window)
    return window.focus_panel


SCREENS: list[Screen] = [
    Screen(
        id="focus.panel_buttons_keep_their_width",
        area="focus",
        prepare=_running_in_bento,
        checks=(
            "The focus panel over Bento while a session runs: every visible button is its own natural "
            "width, at most 8 px wider than its size hint (a button spread to 439 px read as a banner, "
            "not a button)."
        ),
        sources=("desktop/native/settings.py", "desktop/native/layouts/bento.py"),
    ),
    Screen(
        id="focus.panel_reads_as_one_status_line",
        area="focus",
        prepare=_running_in_bento,
        checks=(
            "The focus panel over Bento while a session runs reads as one status line: the homework, the "
            "phase and the countdown sit on one row (tops within 8 px of each other) and read left to "
            "right in that order, not stacked on three rows."
        ),
        sources=("desktop/native/settings.py", "desktop/native/layouts/bento.py"),
    ),
]
