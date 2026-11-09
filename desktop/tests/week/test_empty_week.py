"""A week with nothing in it says where to start, and the hours come back with the first thing added."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest
from PySide6.QtCore import QDate, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractButton, QApplication, QDialog, QLabel, QPushButton

from desktop.native.calendar import sunday_due
from desktop.native.layouts.empty import EMPTY_BUTTON, EMPTY_HEADING, EMPTY_LINE
from desktop.native.widgets import HomeworkDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window as light  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_pastnext import classic_week
from desktop.tests.window_support import qapp, settled  # noqa: F401


@pytest.fixture()
def window(qapp: QApplication, light: NativeWindow) -> NativeWindow:
    """A new account just past setup, with no school block: Today's app, on Week."""
    return classic_week(qapp, light)


def shown(window: NativeWindow) -> object:
    return window.planner.currentWidget()


def test_a_new_accounts_week_offers_one_button_instead_of_empty_hours(qapp, window) -> None:
    assert window.session.blocks == [] and window.session.assignments == {}
    assert shown(window) is window.empty_week
    assert window.week_table.isVisible() is False
    words = [label.text() for label in window.empty_week.findChildren(QLabel)]
    assert words == [EMPTY_HEADING, EMPTY_LINE]
    buttons = [button for button in window.empty_week.findChildren(QPushButton) if button.isVisible()]
    assert [button.text() for button in buttons] == [EMPTY_BUTTON]
    # The top bar stays: where you are, the views, Plan and More.
    for name in ("weekTitle", "viewWeek", "solveButton", "moreButton"):
        assert window.findChild(QLabel if name == "weekTitle" else QAbstractButton, name).isVisible(), name

    window.findChild(QAbstractButton, "viewDay").click()
    settled(qapp, window)
    assert shown(window) is window.empty_week, "Today's app's Day of an empty week says the same"
    window.findChild(QAbstractButton, "viewMonth").click()
    settled(qapp, window)
    assert shown(window) is window.month_grid, "Month is a calendar, empty or not"


def test_the_button_opens_the_homework_editor_and_the_hours_come_back(qapp, window, monkeypatch) -> None:
    opened: list[HomeworkDialog] = []

    def add(dialog: HomeworkDialog) -> int:
        opened.append(dialog)
        dialog.title.setText("Math worksheet")
        dialog.due.date.setDate(QDate.fromString(sunday_due(window.session.week_start)[:10], "yyyy-MM-dd"))
        dialog.accept()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(HomeworkDialog, "exec", add)
    QTest.mouseClick(window.empty_week.add, Qt.MouseButton.LeftButton)
    settled(qapp, window)
    assert len(opened) == 1
    assert [item["title"] for item in window.session.assignments.values()] == ["Math worksheet"]
    wait_until(qapp, lambda: shown(window) is window.week_table)
    assert window.week_table.isVisible()


def test_a_fixed_time_brings_the_hours_back_and_undo_empties_the_week_again(qapp, window) -> None:
    session = window.session
    session.add_block(
        {
            "id": "piano",
            "title": "Piano",
            "kind": "locked",
            "category": "extra",
            "start": "17:00",
            "duration_min": 30,
            "days": [3],
        }
    )
    session.save()
    settled(qapp, window)
    assert shown(window) is window.week_table
    session.undo()
    settled(qapp, window)
    assert session.blocks == []
    assert shown(window) is window.empty_week


def test_a_student_with_homework_keeps_the_hours_on_an_empty_week(qapp, window) -> None:
    """Every week nobody has saved is empty, so next week is empty for everyone. It offers last week
    and routines once the student has homework anywhere."""
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
    assert shown(window) is window.week_table
    window.findChild(QPushButton, "nextWeek").click()
    wait_until(qapp, lambda: not session.busy)
    settled(qapp, window)
    assert session.blocks == []
    assert shown(window) is window.week_table
    assert window.empty_week.isVisible()


def test_a_design_of_its_own_draws_its_own_empty_week(qapp, window) -> None:
    window._layout = {"main": "bento", "day": "one", "options": {}}
    window._on_week()
    assert shown(window) is not window.empty_week
    assert shown(window).layout_id == "bento"
