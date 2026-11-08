# ruff: noqa: F811
# Fixtures are imported by name, so a test taking one as an argument redefines it.
"""Setup's First homework page: the example in the empty box, up to three homework, and the due date
that starts on the next school day."""

from __future__ import annotations

from datetime import date

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QModelIndex, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTableView

from desktop.native.setup import DONE, FIRST, next_school_day
from desktop.tests.setup.support_wizard import opened
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

# The clock starts on Thursday 5 November 2026: the next school day is Friday the 6th, and the next
# Tuesday is the 10th.
NEXT_SCHOOL_DAY = "2026-11-06"
NEXT_TUESDAY = "2026-11-10"


def test_first_homework_takes_up_to_three(qapp: QApplication) -> None:
    setup = opened(qapp)
    setup._show(FIRST)
    assert len(setup.homework_rows) == 1
    setup.add_homework.click()
    setup.add_homework.click()
    assert len(setup.homework_rows) == 3
    assert not setup.add_homework.isEnabled()
    setup._add_homework_row()
    assert len(setup.homework_rows) == 3, "a fourth is refused however it is asked for"
    due = setup.homework_rows[0].due
    assert due.date.calendarPopup()
    assert due.value() == NEXT_SCHOOL_DAY, "due the next school day, with no time"
    setup.close()


def test_the_example_homework_is_words_in_an_empty_box_and_adds_nothing(qapp: QApplication) -> None:
    """A grey 'History essay' read as a filled value, and Done then said None yet. The example is not
    added, so a student who leaves it is told, truly, that none is set."""
    setup = opened(qapp)
    setup._show(FIRST)
    field = setup.homework_rows[0].name
    assert field.placeholderText() == "e.g. History essay"
    assert field.text() == ""
    assert setup.first_homework() == []
    setup._go_next()
    assert setup.step == DONE
    assert setup.summary_text()[4] == "None yet"
    setup.close()


def test_a_homework_typed_over_the_example_is_listed_on_done(qapp: QApplication) -> None:
    setup = opened(qapp)
    setup._show(FIRST)
    setup.homework_rows[0].name.setText("Math worksheet")
    setup._go_next()
    assert setup.summary_text()[4] == "Math worksheet"
    setup.close()


def test_a_date_nobody_touched_follows_the_school_days_picked_earlier(qapp: QApplication) -> None:
    setup = opened(qapp)
    setup.school_days.set_days([1])
    setup._show(FIRST)
    assert setup.homework_rows[0].due.value() == NEXT_TUESDAY
    setup.close()


def test_a_date_the_student_chose_is_left_where_it_is(qapp: QApplication) -> None:
    setup = opened(qapp)
    row = setup.homework_rows[0]
    row.due.set_value("2031-05-06")
    setup.school_days.set_days([2])
    setup._show(FIRST)
    assert row.due.value() == "2031-05-06"
    setup.close()


def test_the_next_school_day_is_after_today_and_on_a_school_day() -> None:
    assert next_school_day([], date(2026, 10, 3)) == "2026-10-04", "no school days: tomorrow"
    # Saturday 3 October 2026: the next of Monday to Friday is Monday the 5th.
    assert next_school_day([0, 1, 2, 3, 4], date(2026, 10, 3)) == "2026-10-05"
    assert next_school_day([4], date(2026, 10, 2)) == "2026-10-09", "after today, not today"


def test_the_calendar_in_setup_opens_on_the_due_month_with_every_day_of_it(qapp: QApplication) -> None:
    """Its grid drew only the weekday letters and one square, because the month's grid Qt makes again
    when the popup opens was not the one the calendar had kept."""
    setup = opened(qapp)
    setup._show(FIRST)
    field = setup.homework_rows[0].due.date
    QTest.mouseClick(
        field,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(field.width() - 6, field.height() // 2),
    )
    month = field.calendarWidget()
    wait_until(qapp, lambda: month.parentWidget().isVisible(), what="the calendar popup opening")
    view = month.findChild(QTableView, "qt_calendar_calendarview")
    model = view.model()
    assert (month.yearShown(), month.monthShown()) == (2026, 11)
    assert model.index(0, 0).data() == "M", "the weekday row"
    shown = {
        int(model.index(row, column, QModelIndex()).data())
        for row in range(1, model.rowCount())
        for column in range(model.columnCount())
    }
    assert set(range(1, 31)) <= shown, "every day of November is in the grid"
    month.parentWidget().hide()
    setup.close()
