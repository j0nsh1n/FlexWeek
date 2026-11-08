"""Dragging in every design, not only Today's app: homework and blocks put down at a time, by one rule
and in the same words everywhere, through the window's one hand.
"""

# ruff: noqa: E402, F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.hours.geometry import Span
from desktop.native.hours.hand import Gesture, Held, Place
from desktop.native.hours.zoom import HoursScroll
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_design_plan import (
    SIZE,
    named,
    placed,
    plan_week,
    session_of,
    settled,
    spin,
    use,
)
from desktop.tests.window_support import qapp  # noqa: F401


@pytest.fixture()
def window(qapp: QApplication, open_light: Callable[..., NativeWindow]) -> NativeWindow:
    """This week: School Monday to Friday 08:00-14:30, the History essay on Thursday 19:00-20:00, and
    a Math worksheet that still needs a time. The clock is held at Thursday 10:00."""
    return plan_week(qapp, open_light(SIZE))


def test_clay_week_day_name_opens_the_day_without_placing_homework(
    qapp: QApplication, window: NativeWindow
) -> None:
    view = use(qapp, window, "clay")
    pick = named(view, "clayDay5")
    QTest.mouseClick(pick, Qt.MouseButton.LeftButton)
    settled(qapp, window)
    assert window.session.planner_view == "day"
    assert (
        window.session.selected_day
        == (date.fromisoformat(window.session.week_start) + timedelta(days=5)).isoformat()
    )
    assert placed(window, "math")[1] is None


def test_a_drop_after_the_due_date_is_refused_and_changes_nothing(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Homework due on Friday, carried to Saturday: the hand is told why while it is held, and a
    placement that reaches the window anyway is refused in the same words and saves nothing."""
    window.session.add_homework(
        {
            "id": "poster",
            "title": "Science poster",
            "due": (date.fromisoformat(window.session.week_start) + timedelta(days=4)).isoformat() + "T23:59",
            "estimate_min": 60,
            "revision": 0,
        }
    )
    window.session.save()
    settled(qapp, window)
    poster_id = session_of(window, "poster")["id"]
    saturday = Span(5, 17 * 60, 18 * 60)
    said = window._hand_judge(poster_id, -1, saturday)
    # The app's own words use contractions ("it's due").
    assert (said.ok, said.words) == (False, "That ends after it's due, so it stayed where it was.")
    revision = window.session.revision
    window.hand.commit(Place(poster_id, saturday))
    settled(qapp, window)
    assert placed(window, "poster")[1] is None
    assert window.session.message == said.words
    assert window.session.revision == revision


def test_a_drop_while_a_save_is_under_way_lands_once_it_is_done(
    qapp: QApplication, window: NativeWindow
) -> None:
    use(qapp, window, "clay")
    window.session.add_block(
        {
            "id": "band",
            "title": "Band",
            "kind": "locked",
            "category": "extra",
            "start": "16:00",
            "duration_min": 60,
            "days": [1],
        }
    )
    window.session.save()
    assert window.session.busy
    math_id = session_of(window, "math")["id"]
    window.hand.commit(Place(math_id, Span(4, 17 * 60, 18 * 60)))
    settled(qapp, window)
    wait_until(qapp, lambda: placed(window, "math")[1] is not None)
    settled(qapp, window)
    assert placed(window, "math") == ([4], "17:00", True)
    assert not window.session.conflict
    assert any(block["id"] == "band" for block in window.session.blocks)


def test_retro_keeps_the_hours_where_they_were_scrolled_through_a_drop(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Retro lays its windows out again after a drop, and for a moment the hours had a little less to
    scroll. The bar was pulled back to that shorter end and left there, so the hours jumped by a few
    pixels, or 22 at another size, under the student's pointer."""
    window.resize(1280, 800)
    view = use(qapp, window, "retro")
    scroll = view.findChild(HoursScroll, "retroWeekScroll")
    assert scroll is not None
    wait_until(qapp, lambda: scroll.verticalScrollBar().maximum() > 0)
    spin(qapp)
    bar = scroll.verticalScrollBar()
    bar.setValue(bar.maximum())
    qapp.processEvents()
    scrolled = bar.value()
    window.hand.commit(Place(session_of(window, "math")["id"], Span(4, 17 * 60, 18 * 60)))
    settled(qapp, window)
    wait_until(qapp, lambda: placed(window, "math")[1] == "17:00")
    spin(qapp, 20)
    assert (bar.value(), bar.maximum()) == (scrolled, scrolled)


def test_a_design_holds_its_renders_from_the_press_and_has_the_windows_hand(
    qapp: QApplication, window: NativeWindow
) -> None:
    """A design is given the window's one hand, and a new scene waits from the moment anything is
    pressed, not from the moment it starts to move."""
    view = use(qapp, window, "timeline")
    assert view.hand is window.hand
    window.hand.press(window, Held(Gesture.PLACE, "Essay", 60, "essay"), QPoint(20, 20))
    assert view._dragging, "a press, before any movement, holds the design's renders"
    window.hand.cancel()
    assert not view._dragging
