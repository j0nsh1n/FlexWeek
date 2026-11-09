"""Unfinished homework from last week shows once, then folds into the More count; Dismiss hides it
and the toolbar reopens it."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import date, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.window_support import qapp, settled, wait_until  # noqa: F401


def test_unfinished_collapses_to_the_more_count_after_the_first_showing(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    session = window.session
    current = session.week_start
    previous = (date.fromisoformat(current) - timedelta(days=7)).isoformat()
    session.load_week(previous)
    wait_until(qapp, lambda: session.week_start == previous and not session.busy)
    session.add_homework(
        {
            "id": "late",
            "title": "Late essay",
            "due": previous + "T21:00",
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.save()
    wait_until(qapp, lambda: not session.busy)
    session.load_week(current)
    wait_until(qapp, lambda: session.week_start == current and not session.busy)
    settled(qapp, window)
    items = session.unfinished()
    assert items
    panel = window.unfinished_panel
    more = window.more_button
    reopen = window.findChild(QPushButton, "unfinishedOpen")
    assert reopen is not None
    panel.set_items(items)
    assert panel.isVisible()
    panel.findChild(QPushButton, "unfinishedDismiss").click()
    qapp.processEvents()
    assert not panel.isVisible() and more.accessibleName() == "More"
    assert window.solve_button.accessibleName() == "Plan my homework, 1 homework still needs time"
    reopen.click()
    qapp.processEvents()
    assert panel.isVisible()
