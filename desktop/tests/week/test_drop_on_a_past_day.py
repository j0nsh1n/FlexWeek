"""With the clock on Thursday, a block cannot be dropped on an earlier day, and the student is told
why; changing one day of a repeating block on a past day still splits that day out."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import CLOCK
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.week.support_weekview import essay_week, send_mouse  # noqa: F401
from desktop.tests.window_support import qapp, settled  # noqa: F401

# A drop on an earlier day than today: that day is over (1.0.0 decision on the past-time sentence).
DAY_OVER = "That time has passed. The day is over, so choose another day."


def put_the_clock_on_thursday(qapp: QApplication, window: NativeWindow) -> None:
    """The clock on Thursday; the essay sits Wednesday, so dragging it to Monday is in the past."""
    from desktop.native.weekmodel import set_clock_24h

    set_clock_24h(False)
    session = window.session
    thursday = datetime.fromisoformat(session.week_start) + timedelta(days=3, hours=12)
    CLOCK.set(thursday)
    session.save()
    settled(qapp, window)


def test_a_drop_on_a_past_day_is_refused_and_says_why(
    qapp: QApplication,
    essay_week: NativeWindow,
) -> None:
    window = essay_week
    put_the_clock_on_thursday(qapp, window)
    essay = next(b for b in window.session.blocks if b.get("assignment_id") == "math")
    before = [dict(b) for b in window.session.blocks]
    # Wednesday to Monday: a different day already past, so it is over. Synthetic moves never leave
    # the origin column (Hand asks widgetAt), so the judge is the drop rule the window uses on release.
    verdict = window._judge_span(essay["id"], 2, 0, 17 * 60, 17 * 60 + 45)
    assert (verdict.ok, verdict.words) == (False, DAY_OVER)
    window._move_block(essay["id"], 2, 0, 17 * 60, 17 * 60 + 45)
    assert window.session.blocks == before
    assert essay["days"] == [2]


def test_moving_one_day_of_a_series_on_a_past_day_still_splits(
    qapp: QApplication,
    essay_week: NativeWindow,
) -> None:
    """A drop onto a different past day is refused. Changing Wednesday's School time, with the clock
    on Thursday, still splits that day's occurrence: the week-series-one-day gesture."""
    window = essay_week
    put_the_clock_on_thursday(qapp, window)
    session = window.session
    session.add_block(
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "category": "class",
            "start": "08:00",
            "duration_min": 390,
            "days": [0, 1, 2, 3, 4],
        }
    )
    session.save()
    settled(qapp, window)
    hours = window.week_table.hours
    hours.reveal(2, 8 * 60, 11 * 60)
    start = hours.point_for(2, 9 * 60)
    end = hours.point_for(2, 10 * 60)
    send_mouse(hours, QEvent.Type.MouseButtonPress, start, True)
    for step in range(1, 9):
        send_mouse(hours, QEvent.Type.MouseMove, start + (end - start) * step / 8, True)
    send_mouse(hours, QEvent.Type.MouseButtonRelease, end, False)
    settled(qapp, window)
    school = sorted((tuple(b["days"]), b["start"]) for b in session.blocks if b["title"] == "School")
    assert school == [((0, 1, 3, 4), "08:00"), ((2,), "09:00")]
