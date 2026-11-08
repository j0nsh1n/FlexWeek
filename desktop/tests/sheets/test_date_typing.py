"""A date typed with no year is the next one that day and month come round, and the box that takes the
year in the picker's header has no arrows. How that box is sized and styled is a picture:
screens_sheets_h7.py."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QDate, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractSpinBox, QSpinBox, QToolButton, QVBoxLayout, QWidget

from desktop.native.fields import DateField
from desktop.native.widgets import DueField
from desktop.tests.sheets.support_date_picker import dressed
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import free, qapp  # noqa: F401

FORMAT = "ddd d MMM yyyy"
WEEKDAY, DAY, MONTH, YEAR = range(4)


def shown(field: DateField) -> QWidget:
    host = QWidget()
    QVBoxLayout(host).addWidget(field)
    host.show()
    field.activateWindow()
    field.setFocus()
    wait_until(None, field.isVisible, what="the date field showing")
    return host


def type_into(field: DateField, section: int, words: str) -> None:
    """Select one part of the date, as a click on it does, and type over it."""
    field.setCurrentSectionIndex(section)
    field.setSelectedSection(field.currentSection())
    QTest.keyClicks(field, words)


def commit(field: DateField) -> None:
    QTest.keyClick(field, Qt.Key.Key_Return)


def test_a_day_and_month_typed_with_no_year_mean_the_next_time_they_come_round(
    qapp,  # noqa: F811
) -> None:
    today = QDate(2026, 10, 3)
    field = DateField(today)
    field.setDisplayFormat(FORMAT)
    field.today = today
    host = shown(field)
    type_into(field, DAY, "1")
    type_into(field, MONTH, "Jan")
    commit(field)
    assert field.date() == QDate(2027, 1, 1), "1 January 2026 is gone; the next one is in 2027"
    free(host)


def test_a_day_and_month_still_to_come_this_year_keep_this_year(qapp) -> None:  # noqa: F811
    today = QDate(2026, 10, 3)
    field = DateField(today)
    field.setDisplayFormat(FORMAT)
    field.today = today
    host = shown(field)
    type_into(field, DAY, "20")
    type_into(field, MONTH, "Dec")
    commit(field)
    assert field.date() == QDate(2026, 12, 20)
    free(host)


def test_a_year_that_was_typed_is_kept_even_when_it_is_past(qapp) -> None:  # noqa: F811
    today = QDate(2026, 10, 3)
    field = DateField(today)
    field.setDisplayFormat(FORMAT)
    field.today = today
    host = shown(field)
    type_into(field, YEAR, "2025")
    commit(field)
    assert field.date().year() == 2025
    free(host)


def test_a_date_picked_or_set_in_code_is_never_moved(qapp) -> None:  # noqa: F811
    field = DateField(QDate(2026, 10, 3))
    field.today = QDate(2026, 10, 3)
    host = shown(field)
    field.setDate(QDate(2026, 9, 1))
    commit(field)
    assert field.date() == QDate(2026, 9, 1), "a past date is for the saving to judge, not typing"
    free(host)


def test_the_due_field_counts_from_the_day_it_is_given(qapp) -> None:  # noqa: F811
    due = DueField("2026-09-14", "probe", today="2026-09-14")
    host = shown(due.date)
    type_into(due.date, DAY, "1")
    type_into(due.date, MONTH, "Jan")
    commit(due.date)
    assert due.value() == "2027-01-01"
    free(host)


def test_the_year_box_in_the_picker_has_no_arrows_over_its_digits(qapp) -> None:  # noqa: F811
    host, _palette = dressed("light-frost")
    field = DateField(QDate(2026, 10, 3))
    QVBoxLayout(host).addWidget(field)
    host.resize(500, 400)
    host.show()
    qapp.processEvents()
    QTest.mouseClick(
        field,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(field.width() - 6, field.height() // 2),
    )
    month = field.calendarWidget()
    wait_until(qapp, month.isVisible, what="the month opening")
    month.findChild(QToolButton, "qt_calendar_yearbutton").click()

    def year_box() -> QSpinBox:
        # Found afresh each time: the Python object found before the events are handled is gone after them.
        return month.findChild(QSpinBox, "qt_calendar_yearedit")

    wait_until(qapp, lambda: year_box().isVisible(), what="the year box showing")
    assert year_box().buttonSymbols() == QAbstractSpinBox.ButtonSymbols.NoButtons, "no arrows over its digits"
    free(host)
