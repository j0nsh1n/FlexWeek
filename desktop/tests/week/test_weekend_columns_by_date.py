"""Saturday and Sunday with nothing on them take less of the week wherever they fall: a week from
Wednesday 23 September 2026 runs to Tuesday 29, so Saturday 26 and Sunday 27 are its fourth and fifth
columns, and Monday 28 and Tuesday 29 its last two, which keep a weekday's width."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.hours.classic import ClassicWeek, empty_days  # noqa: E402
from desktop.native.look import resolved_palette  # noqa: E402
from desktop.native.weekmodel import build_week  # noqa: E402
from desktop.tests.light_app import window  # noqa: E402, F401
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
