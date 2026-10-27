"""1.0.0 planning screen: shared bar, Agenda rail pick A, quiet Week chrome."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

from desktop.native.hours.rail import RAIL_PX
from desktop.native.look import sanitize_look
from desktop.native.tokens import SPACING
from desktop.native.window import NativeWindow
from desktop.tests.test_1br_left_over_guards import overdue_this_week
from desktop.tests.test_more_count import more_row
from desktop.tests.test_week_side import chips, seeded
from desktop.tests.window_support import (  # noqa: F401
    qapp,
    server,
    settled,
    signed_out,
    wait_until,
    window,
)


def week_list_action(native: NativeWindow):
    native._sync_more_menu()
    for action, button in native._more_pairs:
        if button.objectName() == "weekListRow":
            return action
    raise AssertionError("More has no Week as a list")


def test_the_week_has_no_status_strip_and_week_as_a_list_lives_in_more(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    seeded(qapp, window)
    assert window.findChild(QWidget, "weekStatusStrip") is None
    assert window.findChild(QLabel, "weekStatusNext") is None
    assert window.findChild(QLabel, "weekStatusOverdue") is None
    assert not window.week_list_row.isVisibleTo(window)
    action = week_list_action(window)
    assert action.text() == "Week as a list"
    assert action.isEnabled()
    card = window.rail.next
    assert (card.label.text(), card.title.text(), card.when.text()) == (
        "Next",
        "Soccer practice",
        "4:00 PM · in 20 min",
    )


def test_plan_carries_the_not_placed_count_and_more_does_not(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    seeded(qapp, window)
    assert window.solve_button.accessibleName() == "Plan my homework, 1 homework still needs time"
    assert window.more_button.accessibleName() == "More"
    assert window.rail.waiting_count.text() == "1"
    assert window.rail.waiting_label.text() == "No time yet · drag onto a day"


def test_the_agenda_rail_lists_next_no_time_yet_and_due_this_week(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    seeded(qapp, window)
    rail = window.rail
    assert rail.isVisible() and not rail.folded and rail.width() == RAIL_PX
    assert not rail.month.isVisible()
    assert not rail.focus.isVisible()
    assert not rail.show_month.isVisible()
    card = rail.next
    assert (card.label.text(), card.title.text(), card.when.text(), card.then.text()) == (
        "Next",
        "Soccer practice",
        "4:00 PM · in 20 min",
        "Then Dinner at 6:30 PM",
    )
    assert not card.start_focus.isVisible()
    focused = [
        row.findChild(QLabel, "railNextRowTitle").text()
        for row in rail.next.rest.findChildren(QWidget, "railNextRow")
        if row.findChild(QPushButton, "railNextRowFocus") is not None
    ]
    assert focused == ["History essay"]
    assert [chip.accessibleName() for chip in chips(window)] == ["Math worksheet · 1 h"]
    due = [
        (row.findChild(QLabel, "railDueTitle").text(), row.findChild(QLabel, "railDueWhen").text())
        for row in rail.findChildren(QWidget, "railDueRow")
        if row.isVisible()
    ]
    assert due == [
        ("Chem lab report", "Sun"),
        ("History essay", "Sun"),
        ("Math worksheet", "Sun"),
    ]


def test_the_agenda_rail_has_no_count_pill_and_headings_in_ink(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    seeded(qapp, window)
    sheet = window.styleSheet()
    waiting = sheet.split("QLabel#railWaitingCount {")[1].split("}")[0]
    assert "background:" not in waiting
    assert "border-radius" not in waiting
    assert "padding:" not in waiting
    assert window.rail.waiting_count.text() == "1"
    assert window.rail.waiting_count.isVisible()
    labels = sheet.split('QLabel[railLabel="true"] {')[1].split("}")[0]
    assert "color: " in labels
    assert window.rail.next.label.property("railLabel") is True
    assert window.rail.waiting_label.property("railLabel") is True
    assert window.rail.due_label.property("railLabel") is True
    assert window.rail.sections.spacing() == SPACING[4]


def test_the_week_title_opens_the_mini_month(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    seeded(qapp, window)
    assert not window.month_pop.isVisible()
    assert not window.rail.month.isVisible()
    QTest.mouseClick(window.week_title, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    assert window.month_pop.isVisible()
    week = date.fromisoformat(window.session.week_start)
    shown = [day.isoformat() for day in window.month_pick.dates.dates()]
    # The month shown is the one holding this week; two weeks on can fall past its last row
    # (the week of 19 Oct 2026 is one), so the test then goes two weeks back instead.
    later = week + timedelta(days=14)
    if later.isoformat() not in shown:
        later = week - timedelta(days=14)
    assert later.isoformat() in shown, "a week two weeks away is on the month shown"
    QTest.mouseClick(
        window.month_pick.dates,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        window.month_pick.dates.date_point(later.isoformat()).toPoint(),
    )
    wait_until(qapp, lambda: window.session.week_start == later.isoformat() and not window.session.busy)
    assert not window.month_pop.isVisible()


def test_large_text_puts_the_date_under_the_day_name(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    seeded(qapp, window)
    label = window.week_table.findChild(QLabel, "weekDayName0")
    before = label.sizeHint().height()
    window._look = sanitize_look({"preset": "default", "knobs": {"text": "large"}})
    window._apply_appearance()
    for _ in range(5):
        qapp.processEvents()
    assert label._twoline() is True
    assert label.sizeHint().height() > before
    assert window.findChild(QWidget, "weekStatusStrip") is None
    assert week_list_action(window).isEnabled()


def test_overdue_homework_that_already_has_a_time_stays_in_unfinished(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    overdue_this_week(qapp, window)
    window._on_week()
    qapp.processEvents()
    assert window.rail.none_waiting.text() == "Everything has a time."
    assert window.more_button.accessibleName() == "More"
    assert window.solve_button.accessibleName() == "Plan my homework"
    assert more_row(window) == (True, "Unfinished\tNone left")
    window._show_unfinished()
    settled(qapp, window)
    assert window.unfinished_panel.isVisibleTo(window)


def test_the_next_rows_keep_the_keyboard_as_the_minutes_pass(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    """The clock redraws Next every minute; a row's Start focus with the keyboard on it stays put, and
    each one says whose focus it starts."""
    seeded(qapp, window)
    rail = window.rail
    button = rail.next.rest.findChild(QPushButton, "railNextRowFocus")
    assert button.accessibleName() == "Start focus on History essay"
    window.activateWindow()
    button.setFocus(Qt.FocusReason.TabFocusReason)
    qapp.processEvents()
    today, minute = rail._today, rail._minute
    for later in (1, 2, 3):
        rail.set_clock(today, minute + later)
        qapp.processEvents()
    assert rail.next.when.text() == "4:00 PM · in 17 min"
    assert rail.next.rest.findChild(QPushButton, "railNextRowFocus") is button
    assert button.hasFocus()


def test_ctrl_shift_l_opens_the_week_list_and_esc_returns_focus(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    seeded(qapp, window)
    gear = window.settings_gear
    window.activateWindow()
    gear.setFocus(Qt.FocusReason.OtherFocusReason)
    qapp.processEvents()
    QTest.keyClick(
        window.windowHandle(),
        Qt.Key.Key_L,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    )
    for _ in range(3):
        qapp.processEvents()
    assert window.week_list_panel.isVisible()
    assert QApplication.focusWidget() is window.week_access_list
    assert window.week_access_list.currentRow() == 0
    QTest.keyClick(window.windowHandle(), Qt.Key.Key_Escape)
    for _ in range(3):
        qapp.processEvents()
    assert not window.week_list_panel.isVisible()
    assert QApplication.focusWidget() is gear


def test_more_week_as_a_list_opens_the_list_over_the_grid(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    seeded(qapp, window)
    before = window.planner.mapTo(window, window.planner.rect().topLeft()).y()
    week_list_action(window).trigger()
    for _ in range(3):
        qapp.processEvents()
    assert window.week_list_panel.isVisible()
    assert window.week_access_list.isVisibleTo(window)
    assert window.planner.mapTo(window, window.planner.rect().topLeft()).y() == before
    week_list_action(window).trigger()
    for _ in range(3):
        qapp.processEvents()
    assert not window.week_list_panel.isVisible()
