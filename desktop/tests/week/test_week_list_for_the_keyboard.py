"""The week for the keyboard and a screen reader: Ctrl+Shift+L opens a list of the week's blocks that names
each with its day and times and opens one on Enter; the list comes before the grid in Tab order; the grid
and the mini month have accessible names; the list takes no room until the keyboard asks for it."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import date

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QListWidget, QWidget

from desktop.native.hours.canvas import HoursCanvas
from desktop.native.hours.rail import MonthCard
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.sheets.support_keys import press
from desktop.tests.window_support import qapp, settled  # noqa: F401

CTRL_SHIFT = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier


def school_block() -> dict:
    return {
        "id": "school", "title": "School", "kind": "locked", "category": "class",
        "start": "08:30", "duration_min": 405, "days": [0, 1, 2, 3, 4],
    }


def test_a_week_list_names_each_block_with_its_day_and_times(qapp, window) -> None:
    window.session.add_block(school_block())
    window.session.save()
    settled(qapp, window)
    press(window, Qt.Key.Key_L, CTRL_SHIFT)
    rows = []
    for listing in window.findChildren(QListWidget):
        if listing.isVisible() or listing.isVisibleTo(window):
            for i in range(listing.count()):
                item = listing.item(i)
                rows.append(f"{item.text()} {item.data(Qt.ItemDataRole.AccessibleTextRole) or ''}")
    school = [r for r in rows if "School" in r]
    assert school and any("Monday" in r and "8:30 AM" in r and "3:15 PM" in r for r in school), rows[:10]


def test_the_grid_is_named_week_view_hours(qapp, window) -> None:
    canvases = window.findChildren(HoursCanvas)
    assert canvases and all(c.accessibleName() == "Week view, hours" for c in canvases)


def test_the_week_list_precedes_the_grid_and_enter_opens_a_block(qapp, window, monkeypatch) -> None:
    session = window.session
    session.add_block(school_block())
    settled(qapp, window)
    listing = window.week_access_list
    canvas = window.week_table.hours
    press(window, Qt.Key.Key_L, CTRL_SHIFT)
    assert listing.isVisible()
    cursor = listing.nextInFocusChain()
    seen: list[QWidget] = []
    while cursor is not listing and cursor not in seen:
        seen.append(cursor)
        if cursor is canvas:
            break
        cursor = cursor.nextInFocusChain()
    assert canvas in seen, "week grid is not after the list in Tab order"
    row = next(
        listing.item(index)
        for index in range(listing.count())
        if listing.item(index).data(Qt.ItemDataRole.UserRole) == ("school", 0)
    )
    opened: list[str] = []
    monkeypatch.setattr(window, "_edit_block", opened.append)
    listing.setCurrentItem(row)
    listing.setFocus(Qt.FocusReason.OtherFocusReason)
    session.add_block(
        {"id": "club", "title": "Club", "kind": "locked", "category": "exercise",
         "start": "16:00", "duration_min": 60, "days": [0]}
    )
    settled(qapp, window)
    assert QApplication.focusWidget() is listing
    assert listing.currentItem().data(Qt.ItemDataRole.UserRole) == ("school", 0)
    assert any("Club" in listing.item(index).text() for index in range(listing.count()))
    press(listing, Qt.Key.Key_Return)
    assert opened == ["school"]


def test_the_week_shortcut_and_the_mini_month_have_accessible_names(qapp, window) -> None:
    window.week_table.hours.setFocus(Qt.FocusReason.OtherFocusReason)
    press(window.week_table.hours, Qt.Key.Key_L, CTRL_SHIFT)
    assert QApplication.focusWidget() is window.week_access_list
    month = window.findChild(MonthCard).dates
    assert month.accessibleName().startswith("Month, ")
    # The mini month names its week in the app's date order.
    monday = date.fromisoformat(window.session.week_start[:10])
    week = f"{monday.strftime('%a')} {monday.day} {monday.strftime('%b')}"
    assert month.accessibleDescription() == f"Shows the week of {week}."


def test_the_week_list_is_hidden_until_the_keyboard_reaches_it_and_hides_again_on_escape(
    qapp, window
) -> None:
    # An empty week shows its card instead of the grid, so the grid needs a block to take the keyboard.
    window.session.add_block(school_block())
    settled(qapp, window)
    assert window.more_button.isVisible()
    assert not window.week_list_panel.isVisible()
    window.week_table.hours.setFocus(Qt.FocusReason.OtherFocusReason)
    press(window.week_table.hours, Qt.Key.Key_L, CTRL_SHIFT)
    settled(qapp, window)
    assert QApplication.focusWidget() is window.week_access_list
    assert window.week_list_panel.isVisible()
    press(window.week_access_list, Qt.Key.Key_Escape)
    settled(qapp, window)
    assert QApplication.focusWidget() is window.week_table.hours
    assert not window.week_list_panel.isVisible()
