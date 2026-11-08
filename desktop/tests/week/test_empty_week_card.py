"""A week with nothing in it offers Copy last week and Use a routine, and the grid beside the card
still opens the free-time menu."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QContextMenuEvent
from PySide6.QtWidgets import QApplication, QPushButton

from desktop.native.calendar import sunday_due
from desktop.native.layouts.empty import EMPTY_COPY_LAST, EMPTY_USE_ROUTINE
from desktop.native.widgets import RoutineDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.week.support_weekview import CLASSIC_ONE_DAY, menus  # noqa: F401
from desktop.tests.window_support import qapp, settled, wait_until  # noqa: F401


def test_an_empty_next_week_offers_copy_last_week_and_use_a_routine(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    session = window.session
    window._layout = dict(CLASSIC_ONE_DAY)
    session.add_block(
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "category": "class",
            "start": "08:00",
            "duration_min": 390,
            "days": [0, 1, 2, 3, 4],
        }
    )
    session.save()
    settled(qapp, window)
    window.findChild(QPushButton, "nextWeek").click()
    wait_until(qapp, lambda: not session.busy)
    settled(qapp, window)
    assert session.blocks == []
    assert window.planner.currentWidget() is window.week_table
    card = window.empty_week
    assert card.isVisible()
    buttons = [b.text() for b in card.findChildren(QPushButton) if b.isVisible()]
    assert EMPTY_COPY_LAST in buttons and EMPTY_USE_ROUTINE in buttons


def test_routines_with_none_saved_says_so(qapp: QApplication) -> None:
    dialog = RoutineDialog(None, {}, [], "2026-09-21")
    dialog.show()
    wait_until(qapp, lambda: dialog.isVisible())
    empty = dialog.findChild(type(dialog.empty), "routineEmpty")
    assert empty.text() == "No routines saved yet." and empty.isVisible()
    assert not dialog.list.isVisible()
    dialog.close()
    dialog.deleteLater()
    qapp.processEvents()


def test_a_click_on_the_grid_beside_the_empty_week_card_opens_the_free_time_menu(
    qapp: QApplication,
    window: NativeWindow,
    menus: dict,
) -> None:
    session = window.session
    window._layout = dict(CLASSIC_ONE_DAY)
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
    wait_until(qapp, lambda: not session.busy)
    window.findChild(QPushButton, "nextWeek").click()
    wait_until(qapp, lambda: not session.busy)
    settled(qapp, window)
    assert window.planner.currentWidget() is window.week_table
    card = window.empty_week
    assert card.isVisible() and EMPTY_COPY_LAST in [
        button.text() for button in card.findChildren(QPushButton) if button.isVisible()
    ]
    hours = window.week_table.hours
    hours.reveal(1, 17 * 60, 17 * 60 + 30)
    qapp.processEvents()
    at = hours.point_for(1, 17 * 60)
    parent = card.parentWidget()
    assert parent is window.week_table
    assert not card.geometry().contains(parent.mapFromGlobal(at))
    local = hours.mapFromGlobal(at)
    QApplication.sendEvent(hours, QContextMenuEvent(QContextMenuEvent.Reason.Mouse, local, at))
    assert menus["rows"] and any("Add fixed time" in row for row in menus["rows"][0])
