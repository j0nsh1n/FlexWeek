"""Month pictures that came out of test_layouts_window.py (the lead folds this fragment into
screens_month.py)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtWidgets import QAbstractButton, QApplication

from desktop.native.window import NativeWindow
from desktop.tests.blocks_helper import put_block
from desktop.tests.day.support_layouts_window import school_week, settled, wait_until
from desktop.tests.pictures.screen import Screen


def _unfinished_card_open(window: NativeWindow) -> object:
    qapp = QApplication.instance()
    school_week(window)
    window.resize(1024, 640)
    window.findChild(QAbstractButton, "viewMonth").click()
    settled(qapp, window)
    wait_until(qapp, lambda: window.month_grid.canvas.rows() > 1)
    session = window.session
    monday = date.fromisoformat(session.week_start)
    due = (monday + timedelta(days=4)).isoformat() + "T23:59"
    session.add_homework({"id": "bio", "title": "Bio reading", "due": due, "estimate_min": 60, "revision": 0})
    session.save()
    settled(qapp, window)
    block = next(b for b in session.blocks if b.get("assignment_id") == "bio")
    put_block(session, block["id"], 2, 15 * 60 + 15, 16 * 60 + 15, pinned=True)
    session.save()
    settled(qapp, window)
    # Saturday is held on the session only: on the one clock the Unfinished card stays shut here (known:
    # not understood, do not chase).
    saturday = datetime.fromisoformat(session.week_start) + timedelta(days=5, hours=10)
    session.now_ms = lambda: int(saturday.timestamp() * 1000)
    session.week_changed.emit()
    settled(qapp, window)
    wait_until(qapp, lambda: window.unfinished_panel.isVisible())
    for _ in range(5):
        qapp.processEvents()
    return None


SCREENS: list[Screen] = [
    Screen(
        id="month.unfinished_card_fits_a_small_window",
        area="month",
        prepare=_unfinished_card_open,
        checks=(
            "Month at 1024 x 640 with overdue homework in the open Unfinished panel fits: no scroll bar "
            "(the month's vertical scroll bar maximum is 0), the last row of days ends inside the view, "
            "and the left-over chip is hidden while the panel is open. Closed again, each row is at "
            "least its least height. (Known: the Saturday hold is on the session only; not understood, "
            "do not chase.)"
        ),
        sources=("desktop/native/hours/month.py", "desktop/native/window.py"),
        main=False,
    ),
]
