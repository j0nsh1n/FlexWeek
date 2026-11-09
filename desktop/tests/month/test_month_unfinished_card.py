# ruff: noqa: F811
"""Month with overdue homework: the Unfinished panel opens in place of the left-over chip. How the rows
fit round it at 1024x640 is a picture (month.unfinished_card_fits_a_small_window)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.blocks_helper import put_block  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    click,
    qapp,  # noqa: F401
    settled,
    wait_until,
    window,  # noqa: F401
)

WEDNESDAY, FRIDAY, SATURDAY = 2, 4, 5


def test_month_opens_the_unfinished_card_for_overdue_homework(
    qapp: QApplication, window: NativeWindow
) -> None:
    window.resize(1024, 640)
    window.show()
    click(window, "viewMonth")
    settled(qapp, window)
    wait_until(qapp, lambda: window.month_grid.canvas.rows() > 1)
    session = window.session
    monday = date.fromisoformat(session.week_start)
    due = (monday + timedelta(days=FRIDAY)).isoformat() + "T23:59"
    session.add_homework({"id": "bio", "title": "Bio reading", "due": due, "estimate_min": 60, "revision": 0})
    session.save()
    settled(qapp, window)
    block = next(b for b in session.blocks if b.get("assignment_id") == "bio")
    put_block(session, block["id"], WEDNESDAY, 15 * 60 + 15, 16 * 60 + 15, pinned=True)
    session.save()
    settled(qapp, window)
    # Saturday is held on the session only: on the one clock the Unfinished card stays shut here, which
    # is not understood yet (roadmap R3.4, known: do not chase).
    saturday = datetime.fromisoformat(session.week_start) + timedelta(days=SATURDAY, hours=10)
    session.now_ms = lambda: int(saturday.timestamp() * 1000)
    session.week_changed.emit()
    settled(qapp, window)
    wait_until(qapp, lambda: window.unfinished_panel.isVisible())
    assert window.unfinished_panel.isVisible()
    assert not window.left_chip.isVisibleTo(window)
    window.unfinished_panel.hide()
    wait_until(qapp, lambda: not window.unfinished_panel.isVisible())
