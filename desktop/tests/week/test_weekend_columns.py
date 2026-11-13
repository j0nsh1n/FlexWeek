"""Saturday and Sunday with nothing on them take less of the week, and take their share back when
something is put there."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.hours.classic import EMPTY_MIN_PX, column_widths  # noqa: E402
from desktop.native.weekmodel import build_week  # noqa: E402
from desktop.tests.week.support_hand import GYM, SCHOOL, day_widths, week_view  # noqa: E402
from desktop.tests.window_support import qapp  # noqa: E402, F401


def test_an_empty_weekend_is_narrower_than_the_days_with_something_in_them(qapp: QApplication) -> None:
    """Saturday and Sunday with nothing on them take less of the week, though never less than
    EMPTY_MIN_PX, so a block dropped there can still be read; the five days with something in them
    stay equal; and the columns tile the week with no gap."""
    view = week_view(qapp, (SCHOOL,))
    widths = day_widths(view)
    assert max(widths[:5]) - min(widths[:5]) < 0.01, f"days with something are unequal: {widths}"
    for day in (5, 6):
        assert EMPTY_MIN_PX <= widths[day] < widths[0] - 1, f"day {day} is {widths[day]:.0f} px: {widths}"
    tracks = view.hours.tracks
    assert abs(sum(widths) - (tracks[-1].area.right() - tracks[0].area.left())) < 0.01
    assert all(abs(a.area.right() - b.area.left()) < 0.01 for a, b in zip(tracks, tracks[1:], strict=False))


def test_a_weekend_day_with_something_on_it_is_as_wide_as_a_weekday(qapp: QApplication) -> None:
    view = week_view(qapp, (SCHOOL, GYM))
    widths = day_widths(view)
    assert max(widths[:6]) - min(widths[:6]) < 0.01, f"Saturday has Gym and should be a full day: {widths}"
    assert EMPTY_MIN_PX <= widths[6] < widths[0] - 1, f"Sunday is empty and should be narrower: {widths}"


def test_a_weekend_that_fills_up_widens_and_a_week_that_empties_narrows(qapp: QApplication) -> None:
    view = week_view(qapp, (SCHOOL,))
    narrow = day_widths(view)[5]
    view.set_week(build_week("2026-09-21", [SCHOOL, GYM], {}, None), 3, 15 * 60 + 40)
    qapp.processEvents()
    assert day_widths(view)[5] > narrow + 1, "Saturday did not widen once it had Gym"
    view.set_week(build_week("2026-09-21", [SCHOOL], {}, None), 3, 15 * 60 + 40)
    qapp.processEvents()
    assert abs(day_widths(view)[5] - narrow) < 0.01, "Saturday did not narrow when Gym went"


def test_the_weekend_never_gets_narrower_than_a_block_can_be_read_in() -> None:
    """Where the week itself is narrow, an equal share is already less than the minimum, and the
    weekend keeps it rather than growing past the weekdays; where there is room, it takes 60 %."""
    both = frozenset({5, 6})
    for total in (420.0, 700.0, 900.0, 1400.0, 2100.0):
        widths = column_widths(total, both)
        assert abs(sum(widths) - total) < 0.01, total
        share = total / 7
        assert widths[5] == widths[6] <= share + 0.01, total
        assert widths[5] >= min(EMPTY_MIN_PX, share) - 0.01, total
        assert widths[0] >= share - 0.01, total
    assert column_widths(420.0, both) == [60.0] * 7
    assert column_widths(2100.0, both)[5] == pytest.approx(180.0)
    assert column_widths(1400.0, frozenset({6}))[5] == column_widths(1400.0, frozenset({6}))[0]
    assert column_widths(1400.0, frozenset()) == [200.0] * 7, "with no empty weekend day all are equal"
