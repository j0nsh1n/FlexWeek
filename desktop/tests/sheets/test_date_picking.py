"""The date picker's month: it is the look's own month on every date in a sheet, it is built only when
its popup opens, and it keeps the day and the limits the field was given. How the month is drawn (plain
weekends, a round pick, today ringed, a rounded card with an edge) is a picture: screens_sheets_h7.py."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QDate, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDateEdit, QLabel, QTableView, QWidget

from desktop.native.fields import DateField, LookCalendar
from desktop.native.widgets import HomeworkDialog, RoutineDialog, SpreadDialog
from desktop.tests.sheets.support_date_picker import WEEK, dressed
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import free, qapp  # noqa: F401


def test_text_in_a_test_is_drawn_in_grey_shades_so_its_colour_can_be_read(
    qapp: QApplication,  # noqa: F811
) -> None:
    """`ink` reads a number's colour off its darkest pixel. Drawn in coloured subpixel stripes, a 10 had
    no pixel in the text's colour; conftest keeps text in grey shades on every computer."""
    number = QLabel("10")
    number.setStyleSheet("background: white; color: black; font: 13pt 'Inter'")
    number.resize(60, 30)
    picture = number.grab().toImage()
    across, down = range(picture.width()), range(picture.height())
    shades = {picture.pixelColor(x, y).getRgb()[:3] for x in across for y in down}
    assert len(shades) > 2, "the number was drawn"
    assert all(red == green == blue for red, green, blue in shades), "coloured subpixel stripes"
    free(number)


def test_the_date_calendar_is_not_built_until_its_popup_opens(
    qapp: QApplication,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The month is only for the popup, so building it with the sheet delayed the first frame."""
    from desktop.tests.sheets.support_homework import go_when

    made = 0
    real = LookCalendar.__init__

    def counting(self, *args: object, **kwargs: object) -> None:
        nonlocal made
        made += 1
        real(self, *args, **kwargs)

    monkeypatch.setattr(LookCalendar, "__init__", counting)
    parent, _palette = dressed("light-frost")
    dialog = HomeworkDialog(parent, today=WEEK)
    dialog.show()
    for _ in range(6):
        qapp.processEvents()
    go_when(dialog)
    assert made == 0
    field = dialog.due.date
    QTest.mouseClick(
        field,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(field.width() - 6, field.height() // 2),
    )
    wait_until(qapp, lambda: made == 1, what="the month built when the popup opened")
    month = field.calendarWidget()
    assert isinstance(month, LookCalendar)
    view = month.findChild(QTableView, "qt_calendar_calendarview")
    assert view is not None and view.model().rowCount() > 1
    free(dialog)
    free(parent)


def test_a_month_made_late_still_shows_the_fields_day_and_limits(
    qapp: QApplication,  # noqa: F811
) -> None:
    """The month is made when the field is first used. The day and the limits the field was given
    before that must be the month's too: a due date cannot be picked before its earliest day."""
    parent, _palette = dressed("light-frost")
    field = DateField(parent=parent)
    field.setMinimumDate(QDate(2026, 9, 1))
    field.setMaximumDate(QDate(2026, 12, 31))
    field.setDate(QDate(2026, 10, 14))
    month = field.calendarWidget()
    assert isinstance(month, LookCalendar)
    assert month.minimumDate() == QDate(2026, 9, 1)
    assert month.maximumDate() == QDate(2026, 12, 31)
    assert month.selectedDate() == QDate(2026, 10, 14)
    free(parent)


def test_any_press_on_a_date_field_makes_the_looks_month_first(
    qapp: QApplication,  # noqa: F811
) -> None:
    """Wherever the press lands, the month that opens is the look's, not Qt's plain one: the arrow is
    wider at Large text than at Normal."""
    parent, _palette = dressed("light-frost")
    field = DateField(parent=parent)
    field.resize(220, 32)
    parent.show()
    QTest.mousePress(field, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(150, 16))
    assert isinstance(QDateEdit.calendarWidget(field), LookCalendar)
    QTest.mouseRelease(field, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(150, 16))
    free(parent)


def test_every_date_in_a_sheet_is_picked_on_the_looks_month(
    qapp: QApplication,  # noqa: F811
) -> None:
    parent, _palette = dressed("light-frost")
    homework = HomeworkDialog(parent, today=WEEK)
    routines = RoutineDialog(parent, {}, [], WEEK)
    essay = {"id": "e", "title": "Essay", "due": "2026-09-27", "estimate_min": 60}
    spread = SpreadDialog(parent, essay, WEEK)
    fields = (homework.due.date, routines.findChild(QWidget, "routineDestination"), spread.from_date)
    assert [type(field.calendarWidget()) for field in fields] == [LookCalendar] * 3
    assert all(field.calendarWidget().firstDayOfWeek().name == "Monday" for field in fields)
    for made in (homework, routines, spread):
        free(made)
    free(parent)
