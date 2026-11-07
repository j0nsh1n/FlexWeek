"""Opening the date picker's month and reading its grid. The date picker tests and the date picker
pictures share it; test_setup_first_homework imports `cells`, `ink` and `same`."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QDate, QModelIndex, QRect
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QTableView, QWidget

from backend import clock as wall_clock
from desktop.native.fields import LookCalendar
from desktop.native.look import pack_stylesheet, resolved_palette
from desktop.native.tokens import contrast
from desktop.native.widgets import HomeworkDialog, control_art

WEEK = "2026-09-21"


def dressed(pack: str) -> tuple[QWidget, dict]:
    palette = resolved_palette(pack, False, None, "default")
    made = QWidget()
    made.setStyleSheet(pack_stylesheet(pack, False, None, "default", palette, control_art(palette)))
    made.resize(1280, 800)
    made.show()
    return made, palette


def picked_near_today() -> QDate:
    """A day in this month that is not today, so the month shows both."""
    today = QDate(wall_clock.today())
    tomorrow = today.addDays(1)
    return tomorrow if tomorrow.month() == today.month() else today.addDays(-1)


def opened(qapp: QApplication, parent: QWidget, day: QDate) -> tuple[HomeworkDialog, QWidget, LookCalendar]:
    dialog = HomeworkDialog(parent, today=day.toString("yyyy-MM-dd"), due=day.toString("yyyy-MM-dd"))
    dialog.show()
    month = dialog.due.date.calendarWidget()
    popup = month.parentWidget()
    popup.show()
    for _ in range(6):
        qapp.processEvents()
    return dialog, popup, month


def cells(month: LookCalendar) -> tuple[QTableView, dict[QDate, QRect]]:
    """Each date shown and where it is, read off the month's own grid."""
    view = month.findChild(QTableView, "qt_calendar_calendarview")
    model = view.model()
    shown: dict[QDate, QRect] = {}
    first = QDate(month.yearShown(), month.monthShown(), 1)
    for row in range(1, model.rowCount()):
        for column in range(model.columnCount()):
            index = model.index(row, column, QModelIndex())
            number = int(index.data())
            # Rows before the 1st are the month before; a small number late on is the month after.
            if row <= 2 and number > 20:
                day = first.addMonths(-1)
            elif row >= 4 and number < 15:
                day = first.addMonths(1)
            else:
                day = first
            shown[QDate(day.year(), day.month(), number)] = view.visualRect(index)
    return view, shown


def ink(picture: QImage, rect: QRect, ground: str) -> str:
    """The colour in `rect` that stands out most from `ground`: the number's."""
    colours = {
        picture.pixelColor(x, y).name()
        for x in range(rect.left(), rect.right())
        for y in range(rect.top(), rect.bottom())
    }
    return max(colours, key=lambda colour: contrast(colour, ground))


def same(first: str, second: str) -> bool:
    """One colour, give or take the last bit of each channel that drawing text can change."""
    pairs = zip(QColor(first).getRgb()[:3], QColor(second).getRgb()[:3], strict=True)
    return all(abs(one - two) <= 3 for one, two in pairs)
