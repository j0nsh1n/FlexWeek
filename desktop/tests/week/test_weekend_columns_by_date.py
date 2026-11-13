"""Saturday and Sunday with nothing on them take less of the week wherever they fall: a week from
Wednesday 23 September 2026 runs to Tuesday 29, so Saturday 26 and Sunday 27 are its fourth and fifth
columns, and Monday 28 and Tuesday 29 its last two, which keep a weekday's width. Classic, Timeline and
Bento narrow the same days."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from datetime import date

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QRectF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.hours.classic import ClassicWeek, empty_days  # noqa: E402
from desktop.native.layouts import bento  # noqa: E402
from desktop.native.layouts.timeline import FOLD, _spread, pages_of  # noqa: E402
from desktop.native.look import resolved_palette  # noqa: E402
from desktop.native.weekmodel import build_week  # noqa: E402
from desktop.tests.light_app import window  # noqa: E402, F401
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.week.support_hand import SCHOOL, a_hand  # noqa: E402
from desktop.tests.window_support import qapp  # noqa: E402, F401

WEDNESDAY_WEEK = "2026-09-23"
SATURDAY, SUNDAY, MONDAY, TUESDAY = 3, 4, 5, 6
# School on Wednesday 23 to Friday 25, and on Monday 28 and Tuesday 29.
WEEKDAYS = {**SCHOOL, "days": [0, 1, 2, MONDAY, TUESDAY]}


def narrow(widths: list[float], days: tuple[int, ...]) -> bool:
    return all(widths[day] < widths[0] - 1 for day in days)


def as_wide(widths: list[float], days: tuple[int, ...]) -> bool:
    return all(abs(widths[day] - widths[0]) < 0.01 for day in days)


def test_the_empty_weekend_is_saturday_and_sunday_by_date() -> None:
    assert empty_days(build_week("2026-09-21", [], {}, None)) == {5, 6}
    assert empty_days(build_week(WEDNESDAY_WEEK, [], {}, None)) == {SATURDAY, SUNDAY}
    # From Sunday 20 September: Sunday 20 is the first column and Saturday 26 the last.
    assert empty_days(build_week("2026-09-20", [], {}, None)) == {0, 6}
    # A weekday with nothing on it keeps its width, and a Saturday with something on it too.
    on_saturday = {**SCHOOL, "days": [SATURDAY]}
    assert empty_days(build_week(WEDNESDAY_WEEK, [on_saturday], {}, None)) == {SUNDAY}


def test_classic_narrows_the_saturday_and_sunday_of_a_week_from_wednesday(qapp: QApplication) -> None:
    view = ClassicWeek(a_hand())
    view.set_look(None, resolved_palette("system", False, None))
    view.set_week(build_week(WEDNESDAY_WEEK, [WEEKDAYS], {}, None), 1, 15 * 60 + 40)
    view.resize(980, 500)
    view.show()
    qapp.processEvents()
    view.hours.relayout()
    qapp.processEvents()
    widths = [view.hours.track_for(day).area.width() for day in range(7)]
    assert narrow(widths, (SATURDAY, SUNDAY)), widths
    assert as_wide(widths, (1, 2, MONDAY, TUESDAY)), widths


def test_timeline_narrows_the_saturday_and_sunday_of_a_week_from_wednesday() -> None:
    week = build_week(WEDNESDAY_WEEK, [WEEKDAYS], {}, None)
    tracks = _spread(24, FOLD, empty_days(week), QRectF(0, 0, 1400, 600))
    widths = {track.day: track.area.width() for track in tracks}
    for page in pages_of(FOLD):
        quiet = [day for day in page if day in (SATURDAY, SUNDAY)]
        busy = [day for day in page if day not in (SATURDAY, SUNDAY)]
        assert all(abs(widths[day] - widths[busy[0]]) < 0.01 for day in busy), widths
        assert all(widths[day] < widths[busy[0]] - 1 for day in quiet), widths


def test_bento_narrows_the_saturday_and_sunday_of_a_week_from_wednesday(
    qapp: QApplication, window, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = window.session
    session.follow_first_weekday(2)
    wait_until(qapp, lambda: not session.busy)
    session.add_block(WEEKDAYS)
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    window._layout = {"main": "bento", "day": "one", "options": {}}
    window._apply_appearance()
    window._on_week()
    window.resize(1280, 860)
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    qapp.processEvents()
    assert date.fromisoformat(session.week_start).weekday() == 2
    shown = [item for item in window.findChildren(bento.BentoCanvas) if item.isVisible() and item.day_buttons]
    canvas = shown[0]
    canvas.relayout()
    widths = [canvas.track_for(day).area.width() for day in range(7)]
    assert narrow(widths, (SATURDAY, SUNDAY)), widths
    assert as_wide(widths, (1, 2, MONDAY, TUESDAY)), widths
