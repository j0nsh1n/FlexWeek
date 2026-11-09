"""Where Mission control's week lanes open: through the evening, or with now in view when the evening
does not fit with it. The lanes are a scroll, so the minutes they show are the scroll's position."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.layouts.mission import WEEK_SCALE  # noqa: E402
from desktop.tests.day.support_mission import (  # noqa: E402
    BLOCKS,
    block,
    last_minute_shown,
    minutes_shown,
    shown,
)

SURFACE, SCROLL, CHOSEN = "week", "missionWeekScroll", {}


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-mission-week-opening-test"])


@pytest.mark.parametrize("size", [(1366, 760), (1280, 800), (810, 800)])
def test_the_lanes_of_another_week_open_through_the_evening(
    qapp: QApplication, size: tuple[int, int]
) -> None:
    """With now not in what shows, the lanes open showing the end of the day that has something in it:
    22:00 at the least, plus half an hour, so a name written at the evening's end is not cut off at the
    edge of the lanes, and for a day with a late block, that block's end. The view of the hours is not
    shrunk to get there: it scrolls."""
    week = shown(qapp, size=size, today=None)
    assert last_minute_shown(week, SCROLL) == pytest.approx(22 * 60 + 30, abs=2)
    late = block("late", "locked", [4], "22:00", 75, title="Late", category="extra")
    week = shown(qapp, size=size, blocks=[*BLOCKS, late], today=None)
    assert last_minute_shown(week, SCROLL) == pytest.approx(23 * 60 + 45, abs=2)
    assert week._scrolls["week"].px == WEEK_SCALE.default

@pytest.mark.parametrize("size", [(1280, 800), (810, 800)])
def test_now_is_on_screen_when_the_evening_does_not_fit_with_it(
    qapp: QApplication, size: tuple[int, int]
) -> None:
    """At 08:00 the lanes cannot show both now and 22:30, so now stays near the left edge, with 30 to
    60 minutes of the morning before it, and the evening is a scroll."""
    view = shown(qapp, size=size, surface=SURFACE, minute="08:00", **CHOSEN)
    first, last = minutes_shown(view, SCROLL)
    assert last < 22 * 60 + 30, "the case is one where the evening does not fit"
    assert 8 * 60 - 60 <= first <= 8 * 60 - 30, f"{SURFACE}: the lanes start at {first:.0f}"


@pytest.mark.parametrize("size", [(1280, 800), (810, 800)])
def test_now_and_the_evening_both_show_when_they_fit(qapp: QApplication, size: tuple[int, int]) -> None:
    view = shown(qapp, size=size, surface=SURFACE, minute="15:40", **CHOSEN)
    first, last = minutes_shown(view, SCROLL)
    assert first <= 15 * 60 + 40 <= last
    assert last == pytest.approx(22 * 60 + 30, abs=2), f"{SURFACE}: the lanes end at {last:.0f}"


@pytest.mark.parametrize("minute", ["22:48", "23:50"])
@pytest.mark.parametrize("size", [(1280, 800), (810, 800)])
def test_now_is_on_screen_when_it_is_later_than_the_evening(
    qapp: QApplication, size: tuple[int, int], minute: str
) -> None:
    """Audit #12: opened at 22:48 the lanes showed about 09:00 to 21:00 or ended at 22:30, with now off
    the right edge. The lanes open with now in view at any time of day."""
    view = shown(qapp, size=size, surface=SURFACE, minute=minute, **CHOSEN)
    first, last = minutes_shown(view, SCROLL)
    now = int(minute[:2]) * 60 + int(minute[3:])
    assert first <= now <= last, f"{SURFACE}: now {now} is outside {first:.0f} to {last:.0f}"


@pytest.mark.parametrize(("minute", "today"), [("13:40", None), ("08:00", 3)])
def test_the_lanes_keep_their_opening_while_the_window_settles(
    qapp: QApplication, minute: str, today: int | None
) -> None:
    """A window is laid out in steps, and the lanes are narrower or wider than they started. They
    open where the rule puts them and stay there until the student scrolls: the evening's end at the
    right edge, or now near the left edge when the evening does not fit with it. A wider window may
    fit both, and then the evening wins."""
    view = shown(qapp, size=(1280, 800), minute=minute, today=today)
    for width in (1000, 1200):
        view.resize(width, 800)
        qapp.processEvents()
        first, last = minutes_shown(view, SCROLL)
        if today is None:
            assert 22 * 60 <= last <= 22 * 60 + 60, width
        else:
            assert 8 * 60 - 60 <= first <= 8 * 60 - 30, width
