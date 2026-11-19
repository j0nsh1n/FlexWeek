"""The Day view's words, the agenda's times, My day's actions and where the now line is drawn in the
hours. How the now line and the times look is checked in pictures (week.now-line-through-school,
week.day-agenda-times, week.clay-now-pill)."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QAbstractButton, QApplication

from desktop.native.hours import classic
from desktop.native.weekmodel import clock_label, set_clock_24h
from desktop.native.window import NativeWindow
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_typing import DESIGNS, hours, hours_window  # noqa: F401
from desktop.tests.window_support import qapp  # noqa: F401


def test_day_names_its_date_once(qapp: QApplication, hours_window: NativeWindow) -> None:
    window = hours_window
    window.findChild(QAbstractButton, "viewDay").click()
    wait_until(qapp, lambda: not window.session.busy)
    assert window.day_view.agenda.heading.text() == "Agenda"
    assert window.day_view.name.text() == "Hours"




def test_the_day_agenda_writes_each_time_on_the_twelve_hour_clock(
    qapp: QApplication, hours_window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = hours_window
    window.findChild(QAbstractButton, "viewDay").click()
    window.resize(810, 800)
    wait_until(qapp, lambda: not window.session.busy)
    set_clock_24h(False)
    written: list[str] = []
    wanted = {
        clock_label(value) for item in window.day_view.agenda.list.items for value in (item.start, item.end)
    }

    class Text(QPainter):
        def drawText(self, *args):  # noqa: N802
            if len(args) == 3 and isinstance(args[0], QRectF) and args[2] in wanted:
                written.append(args[2])
            return super().drawText(*args)

    monkeypatch.setattr(classic, "QPainter", Text)
    try:
        window.day_view.agenda.list.grab()
        assert written
        assert any("AM" in words or "PM" in words for words in written), written
    finally:
        set_clock_24h(True)


def test_running_school_has_no_agenda_now_row(qapp: QApplication, hours_window: NativeWindow) -> None:
    from desktop.native.hours.classic import ClassicDay

    window = hours_window
    view = ClassicDay(window.hand, window)
    view.set_day(window.week_table._shown[0], 0, 0, 620)
    for _ in range(4):
        qapp.processEvents()
    assert all(row.item is not None for row in view.agenda.list.rows)
    school = next(row.item for row in view.agenda.list.rows if row.item.block_id == "school")
    assert school.start < 620 < school.end
    assert view.hours.now_min == 620


