"""Where Mission control's day lanes open: through the evening, or with now in view when the evening
does not fit with it. The lanes are a scroll, so the minutes they show are the scroll's position."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.tests.day.support_mission import (  # noqa: E402
    last_minute_shown,
    minutes_shown,
    shown,
)

SURFACE, SCROLL, CHOSEN = "day", "missionDayScroll", {"iso_day": "2026-09-17"}


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-mission-day-opening-test"])


def test_another_days_lanes_open_through_the_evening(qapp: QApplication) -> None:
    """With now not in what shows, the lanes open showing the end of the evening, as the week's do."""
    for size in ((1366, 760), (1280, 800), (810, 800)):
        view = shown(qapp, size=size, surface="day", iso_day="2026-09-16")
        assert last_minute_shown(view, SCROLL) == pytest.approx(22 * 60 + 30, abs=2), size

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


def test_the_day_after_today_opens_through_the_evening_whatever_the_time_now(qapp: QApplication) -> None:
    """Now is not in the day shown when it is another day's, so the evening rule holds for it."""
    view = shown(qapp, size=(1280, 800), surface="day", iso_day="2026-09-18", minute="08:00")
    assert last_minute_shown(view, SCROLL) == pytest.approx(22 * 60 + 30, abs=2)
