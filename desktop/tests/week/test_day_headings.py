"""The headings on Day: 'Hours' is written once whichever day is shown, and 'Agenda' beside it keeps its
name. How they look (size, colour) is a screen: week.day-hours-heading-today and ...-another-day."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.hours import classic as classic_module  # noqa: E402
from desktop.tests.week import support_zoom  # noqa: E402
from desktop.tests.week.support_zoom import SCHOOL, a_day  # noqa: E402

qapp = support_zoom.qapp  # a fixture is found by its name in the test module


def test_days_hours_heading_is_written_once_today_or_not_and_agenda_keeps_its_name(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ "Hours" was the accent on today and a small muted word otherwise, beside "Agenda" in the
    heading size and the text colour. Both headings now read the same, whichever day it is."""
    wrote: list[str] = []

    class Heard(QPainter):
        def drawText(self, *args) -> None:  # noqa: N802
            wrote.append(next(arg for arg in reversed(args) if isinstance(arg, str)))
            super().drawText(*args)

    monkeypatch.setattr(classic_module, "QPainter", Heard)
    for day in (3, 1):
        view = a_day(qapp, [SCHOOL], day)
        wrote.clear()
        view.name.repaint()
        assert [words for words in wrote if words == "Hours"] == ["Hours"], (day, wrote)
    heading = view.agenda.heading
    assert heading.text() == "Agenda" and heading.property("railHeading") is True
