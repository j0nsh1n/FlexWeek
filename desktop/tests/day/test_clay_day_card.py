"""Clay deck's Day: the open card with its summary of the day, what is left today, the arrows and a
carried block asking the window for another day, and the row sliding between days."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QAbstractAnimation, QCursor, QPoint  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget  # noqa: E402
from shiboken6 import isValid  # noqa: E402

from desktop.native import motion  # noqa: E402
from desktop.native.hours.canvas import HoursCanvas  # noqa: E402
from desktop.native.layouts.clay import Card, left_today  # noqa: E402
from desktop.native.weekmodel import build_week, minute_of  # noqa: E402
from desktop.tests.test_weekmodel import BLOCKS, HOMEWORK, TRACE, WEEK  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.week.support_clay import (  # noqa: E402, F401
    at_slots,
    drag,
    front,
    pairs,
    shown,
    slide_day,
    still,
    stop_slide,
    takeover_between_the_pictures,
    visible_scrolls,
)


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-clay-test"])
    yield application


def test_day_opens_the_card_wider_with_its_hours_by_kind_and_what_is_left_today(qapp: QApplication) -> None:
    """Thursday at 13:40: School 08:00-14:30, Dinner 18:00-18:30, the essay 18:45-19:45 and chemistry
    20:00-21:30. Planned is placed homework still ahead (the essay and chemistry, 2 h 30 min), not School."""
    view = shown(qapp, tab="day")
    assert [scroll.objectName() for scroll in visible_scrolls(view)] == ["clayDayScroll"]
    assert [(track.day, track.first, track.last) for track in front(view).tracks] == [(3, 0, 1440)]
    summary = view.findChild(QWidget, "claySummary")
    assert summary.findChild(QLabel, "claySumTitle").text() == "Thursday, 08:00 to 22:00"
    assert pairs(view) == [
        ("School", "6 h 30 min"),
        ("Homework", "2 h 30 min"),
        ("Meals", "30 min"),
        ("Free", "4 h 30 min"),
        ("Planned", "2 h 30 min"),
        ("Free until 22:00", "4 h 30 min"),
        ("Next at 18:00", "in 4 h 20 min"),
    ]


def test_planned_counts_only_what_is_left_of_homework_already_under_way() -> None:
    """At 13:40 the essay from 13:00 to 14:00 has 20 minutes left, and chemistry's 90 at 20:00 are all
    ahead: planned today is 1 h 50 min, not the essay's whole hour on top of chemistry."""
    blocks = [dict(item, start="13:00") if item["id"] == "essay-1" else item for item in BLOCKS]
    planned, _free, _coming = left_today(build_week(WEEK, blocks, HOMEWORK, TRACE), 3, minute_of("13:40"))
    assert planned == 20 + 90


def test_another_day_has_no_left_today(qapp: QApplication) -> None:
    view = shown(qapp, tab="day", day=4)
    assert view.row.front == 4
    assert pairs(view) == [("School", "6 h 30 min"), ("Meals", "30 min"), ("Free", "7 h")]
    assert view.findChild(QLabel, "clayLeftTitle") is None


def test_days_arrows_ask_the_window_for_the_day_either_side_across_the_weeks_edge(
    qapp: QApplication,
) -> None:
    view = shown(qapp, tab="day", day=0)
    opened: list[str] = []
    view.day_activated.connect(opened.append)
    view.findChild(QPushButton, "clayAhead").click()
    view.findChild(QPushButton, "clayBack").click()
    assert opened == ["2026-09-15", "2026-09-13"]
    assert view.row.front == 0


def test_a_block_carried_to_another_day_on_day_takes_the_window_there_when_it_is_let_go(
    qapp: QApplication,
) -> None:
    view = shown(qapp, tab="day")
    opened: list[str] = []
    view.day_activated.connect(opened.append)
    ahead = view.findChild(QPushButton, "clayAhead")
    QCursor.setPos(ahead.mapToGlobal(ahead.rect().center()))
    view.hand.active_changed.emit(True)
    # The row waits half a second of the pointer's own time on the arrow before it moves.
    wait_until(qapp, lambda: view.row.front == 4, what="the row moving after a rest on the arrow")
    assert opened == []
    view.hand.active_changed.emit(False)
    assert opened == [view.scene.week.date_of(4).isoformat()]


def test_a_sideways_drag_on_day_asks_the_window_for_the_day_as_the_arrows_do(qapp: QApplication) -> None:
    view = shown(qapp, tab="day")
    opened: list[str] = []
    view.day_activated.connect(opened.append)
    friday = view.findChild(HoursCanvas, "clayPeek4")
    assert friday.isVisible()
    drag(friday, friday.rect().center(), QPoint(-200, 0))
    assert opened == [view.scene.week.date_of(4).isoformat()]
    # The window has not shown Friday here, so the row went back to Thursday meanwhile.
    assert view.row.front == 3 and at_slots(view, 3)


def test_day_hides_live_side_cards_while_the_row_slides(qapp: QApplication) -> None:
    """Day's render used to _put after the slide had started, which showed the live neighbours
    beside the moving pictures."""
    view = shown(qapp, tab="day")
    motion.apply_ui_effects("normal")
    row = view.row
    row._go(4, "slide")
    assert row._slide.state() == QAbstractAnimation.State.Running
    row.set_summary(view._summary(view.scene, 4))
    assert row._snaps is not None
    live = [card for card in row.findChildren(Card) if card.isVisible()]
    assert live == [], f"live side cards still showing: {[card.day for card in live]}"
    stop_slide(row)


def test_only_one_day_summary_shows_while_the_row_slides(qapp: QApplication) -> None:
    """The new day's summary must not sit live over the baked picture of the old one."""
    view = shown(qapp, tab="day")
    motion.apply_ui_effects("normal")
    row = view.row
    row._go(4, "slide")
    row.set_summary(view._summary(view.scene, 4))
    assert row._snaps is not None
    summaries = [widget for widget in view.findChildren(QWidget, "claySummary") if widget.isVisible()]
    assert summaries == [], "a live claySummary is stacking on the slide's pictures"
    stop_slide(row)


def test_a_summary_replaced_mid_slide_is_the_one_shown_when_it_lands(qapp: QApplication) -> None:
    """Day's summary can be replaced while the row slides. When it lands, the new one shows in the
    row, and the replaced one is never shown again, least of all as a window of its own."""
    view = shown(qapp, tab="day")
    motion.apply_ui_effects("normal")
    row = view.row
    row._go(4, "slide", summary=view._summary(view.scene, 4))
    assert row._snaps is not None
    old = row._summary
    fresh = view._summary(view.scene, 4)
    row.set_summary(fresh)
    stop_slide(row)
    assert row._summary is fresh
    assert fresh.parentWidget() is row and fresh.isVisible(), "the new summary shows once landed"
    assert old is None or not isValid(old) or not old.isVisible(), "the replaced summary stays hidden"


def test_the_end_picture_takes_over_from_the_start_picture_between_15_and_55_percent_on_day(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    takeover_between_the_pictures(slide_day(qapp), monkeypatch)
