"""The Day view's words, the agenda's times, My day's actions and where the now line is drawn in the
hours. How the now line and the times look is checked in pictures (week.now-line-through-school,
week.day-agenda-times, week.clay-now-pill)."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QImage, QPainter
from PySide6.QtWidgets import QAbstractButton, QApplication, QPushButton

from desktop.native.calendar import sunday_due
from desktop.native.hours import classic
from desktop.native.hours.geometry import LinearTrack
from desktop.native.layouts.clay import ClayPainter
from desktop.native.layouts.registry import MATCH, sanitize_layout, tokens_for
from desktop.native.look import resolved_palette
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


def test_my_day_offers_running_late_for_a_late_session(
    qapp: QApplication, hours_window: NativeWindow
) -> None:
    window = hours_window
    session = window.session
    # Due at the end of the held week: a fixed date went past and left nothing to run late on.
    session.add_homework(
        {
            "id": "essay",
            "title": "Essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 60,
            "revision": 0,
        }
    )
    block = next(item for item in session.blocks if item.get("assignment_id") == "essay")
    session.hand_move(block["id"], -1, 3, 19 * 60, 19 * 60 + block["duration_min"])
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    window.findChild(QAbstractButton, "viewMyDay").click()
    for _ in range(4):
        qapp.processEvents()
    late = window.findChild(QPushButton, "dialLate")
    assert late is not None and late.isVisible()


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


@pytest.mark.parametrize("design", DESIGNS)
def test_the_now_line_is_drawn_before_the_blocks_so_their_words_stay_on_top(
    qapp: QApplication, hours_window: NativeWindow, monkeypatch: pytest.MonkeyPatch, design: str
) -> None:
    """During School the line for now shows on School, and School's words are written over it. Drawn
    after the blocks, the line ran through "School" and hid under no block's colour."""
    window = hours_window
    window._layout = sanitize_layout({"main": design})
    window._apply_appearance()
    window._on_week()
    for _ in range(4):
        qapp.processEvents()
    canvas = hours(window).canvas
    canvas.set_week(canvas.occurrences, 3, 10 * 60 + 30)
    painter = canvas.painter
    calls: list[str] = []
    now, block = painter.now, painter.block

    def drew_now(*args, **kwargs):
        calls.append("now")
        return now(*args, **kwargs)

    def drew_block(*args, **kwargs):
        calls.append("block")
        return block(*args, **kwargs)

    monkeypatch.setattr(painter, "now", drew_now)
    monkeypatch.setattr(painter, "block", drew_block)
    assert not canvas.grab().isNull()
    assert "now" in calls, "the line for now was not drawn during School"
    assert calls.index("now") < calls.index("block"), calls


def test_clays_now_pill_takes_the_place_of_the_hour_label_under_it() -> None:
    """The pill left of the hours lies where their labels are. At 10:20 on hours 40 pixels each, the
    10:00 label was written and the pill drawn over it; 11:00, clear of the pill, stays."""
    painting = ClayPainter(tokens_for("clay", MATCH, resolved_palette("light-frost", False, None)), full=True)
    painting.now_minute = 10 * 60 + 20
    pills: list[QRectF] = []
    labels: set[str] = set()

    class Marks(QPainter):
        def drawRoundedRect(self, box, *args):  # noqa: N802
            pills.append(QRectF(box))
            return super().drawRoundedRect(box, *args)

        def drawText(self, box, flags, words):  # noqa: N802
            labels.add(words)
            return super().drawText(box, flags, words)

    track = LinearTrack(0, QRectF(120, 20, 600, 480), first=8 * 60, last=20 * 60)
    picture = QImage(800, 520, QImage.Format.Format_ARGB32)
    paint = Marks(picture)
    paint.setFont(QFont("Inter", 12))
    set_clock_24h(True)
    try:
        painting.hour_labels(paint, track, 56)
        written = set(labels)
        painting.now(paint, track, painting.now_minute)
    finally:
        paint.end()
    assert len(pills) == 1
    assert "11:00" in written, "an hour clear of the pill keeps its label"
    assert "10:00" not in written, "the hour label under the pill is left out"
