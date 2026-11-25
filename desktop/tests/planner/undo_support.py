"""What the Undo toast tests share: a week where Plan has just placed one block and offered Undo."""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from desktop.native.calendar import sunday_due
from desktop.native.window import NativeWindow
from desktop.tests.grid_support import WEDNESDAY, hold_clock
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import settled

PLACED = "Placed 1 homework session."


def add_essay(qapp: QApplication, window: NativeWindow) -> None:
    """One hour of History essay, due Sunday, with the clock held on Wednesday 14:07."""
    session = window.session
    session.add_homework(
        {
            "id": "essay",
            "title": "History essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.save()
    settled(qapp, window)
    hold_clock(window, WEDNESDAY, 14 * 60 + 7)


def planned(qapp: QApplication, window: NativeWindow) -> QPushButton:
    """Add the essay and press Plan; returns with the Undo toast up. Returns the Plan button."""
    add_essay(qapp, window)
    solve = window.findChild(QPushButton, "solveButton")
    QTest.mouseClick(solve, Qt.MouseButton.LeftButton)
    wait_until(
        qapp,
        lambda: window.toast.isVisible() and window.toast.button.isVisible(),
        what="Plan's Undo toast",
    )
    settled(qapp, window)
    assert window.toast.text() == PLACED
    assert window.toast.button.accessibleName() == "Undo"
    assert window.toast.button.text().startswith("Undo")
    return solve


def undo_still_offered(window: NativeWindow) -> tuple[bool, str, bool, str]:
    toast = window.toast
    return toast.isVisible(), toast.text(), toast.button.isVisible(), toast.button.accessibleName()


MATERIAL_PLACED = "Placed 1 of 1 homework sessions"


def planned_in_material(qapp: QApplication, window: NativeWindow) -> QObject:
    """The Material week with the essay added and Plan pressed; returns with Undo offered on the snackbar.
    Returns the QML root."""
    from datetime import datetime, timedelta

    from backend.tests.fake_clock import CLOCK
    from desktop.tests.week.support_material import _click, _qml, _snack
    from desktop.tests.week.support_material_page import fresh_material

    session = window.session
    session.add_homework(
        {
            "id": "essay",
            "title": "History essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.save()
    settled(qapp, window)
    CLOCK.set(datetime.fromisoformat(session.week_start) + timedelta(days=2, minutes=14 * 60 + 7))
    root = fresh_material(qapp, window)
    # The notice's clock waits while its window is not the active one, so the tests look at a window
    # that is.
    window.activateWindow()
    wait_until(qapp, window.isActiveWindow, what="the window to be the active one")
    _click(window, _qml(root, "planHomework"))
    wait_until(
        qapp, lambda: _snack(window).startswith("Placed") and not session.busy, what="Plan's Undo notice"
    )
    settled(qapp, window)
    return root
