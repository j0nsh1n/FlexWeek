"""Today's app's week scrolls a full day at a height where an hour still has edges: midnight and the
end of the day can both be reached, and each day's name opens that day."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QRectF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QScrollArea  # noqa: E402

from desktop.native.hours import canvas as canvas_module  # noqa: E402
from desktop.native.hours.canvas import BlockPainter, HoursCanvas  # noqa: E402
from desktop.native.hours.geometry import FIRST, LAST, LinearTrack  # noqa: E402
from desktop.native.look import resolved_palette  # noqa: E402
from desktop.tests.week.support_hand import SCHOOL, Said, a_hand, week_view  # noqa: E402
from desktop.tests.window_support import qapp  # noqa: E402, F401


def test_midnight_and_the_end_of_the_day_can_be_scrolled_onto_the_week(qapp: QApplication) -> None:
    view = week_view(qapp)
    hours = view.hours
    assert hours.height() > view.scroll.viewport().height()

    hours.reveal(3, FIRST, FIRST + 60)
    qapp.processEvents()
    assert hours.in_view(3, FIRST), "00:00 is not in the hours viewport"
    assert not hours.in_view(3, LAST), "24:00 still counted as reached while it is clipped"

    hours.reveal(3, LAST - 60, LAST)
    qapp.processEvents()
    assert hours.in_view(3, LAST), "24:00 is not in the hours viewport"
    assert not hours.in_view(3, FIRST), "00:00 still counted as reached while it is clipped"


def test_reach_does_not_substitute_the_edge_of_a_partial_track(qapp: QApplication) -> None:
    scroll = QScrollArea()
    scroll.resize(230, 400)
    hours = HoursCanvas(
        a_hand(),
        BlockPainter(resolved_palette("system", False, None)),
        lambda area: [LinearTrack(3, QRectF(10, 10, 180, 1160), first=6 * 60, last=22 * 60)],
    )
    hours.setFixedSize(200, 1180)
    scroll.setWidget(hours)
    scroll.show()
    qapp.processEvents()
    hours.relayout()

    hours.reveal(3, 0, 60)
    qapp.processEvents()
    assert hours.in_view(3, 6 * 60)
    assert not hours.in_view(3, 0)

    hours.reveal(3, 23 * 60, 24 * 60)
    qapp.processEvents()
    assert hours.in_view(3, 22 * 60)
    assert not hours.in_view(3, 24 * 60)


def test_a_day_name_on_the_week_stays_visible_and_opens_that_day(qapp: QApplication) -> None:
    view = week_view(qapp)
    opened: list[int] = []
    view.day_opened.connect(opened.append)
    view.hours.reveal(3, LAST - 60, LAST)
    qapp.processEvents()
    name = view.findChild(QLabel, "weekDayName4")
    assert name is not None and name.isVisible()
    QTest.mouseClick(name, Qt.MouseButton.LeftButton)
    assert opened == [4]


def test_the_hours_end_with_their_end_label(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    """Today's app's Week or Day labels the end of the day as every design does: "24:00", or "12:00 AM"
    on the 12-hour clock."""
    monkeypatch.setattr(canvas_module, "QPainter", Said)
    view = week_view(qapp, (SCHOOL,))
    view.hours.reveal(3, LAST - 60, LAST)
    qapp.processEvents()
    Said.words = []
    view.hours.repaint()
    labels = [text for text, _where in Said.words if text.endswith(":00") and len(text) == 5]
    assert "23:00" in labels and "24:00" in labels, labels
    assert view.hours.track_for(3).last == LAST
