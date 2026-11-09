"""Month in Today's app and in the designs: it stays where the student scrolled it through a refresh,
draws a week left unsaved as the student has it, and judges a chip dropped from a week that is not open
by that chip's own time and homework. A chip let go after a save failed is refused in words."""

# ruff: noqa: E402, F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QAbstractButton, QApplication, QWidget

from desktop.native.hours.hand import MoveDate
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_design_plan import (
    SIZE,
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
    """This week: School Monday to Friday, the History essay on Thursday 19:00-20:00 (due Sunday) and a
    Math worksheet that still needs a time. The clock is held on Thursday 10:00."""
    return plan_week(qapp, open_light(SIZE))


def month_loaded(qapp: QApplication, window: NativeWindow) -> None:
    wait_until(
        qapp,
        lambda: window.session.month_data is not None and not window.session.busy,
        what="the month to arrive",
    )
    spin(qapp)


def open_month_of(qapp: QApplication, window: NativeWindow, iso: str) -> None:
    window.session.open_month(iso[:7])
    month_loaded(qapp, window)


def test_month_stays_where_the_student_scrolled_it_through_a_refresh(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Month opens on the week the student is in, once. It used to scroll back there every time
    anything refreshed, such as a save, undoing the student's own scrolling."""
    window.resize(900, 560)
    window.findChild(QAbstractButton, "viewMonth").click()
    month_loaded(qapp, window)
    bar = window.month_grid.scroll.verticalScrollBar()
    assert bar.maximum() > 0, "the month is taller than the window, so it scrolls"
    bar.setValue(0 if bar.value() else bar.maximum())
    chosen = bar.value()
    window._on_week()
    spin(qapp)
    assert bar.value() == chosen


def test_a_designs_month_stays_where_the_student_scrolled_it_through_a_refresh(
    qapp: QApplication, window: NativeWindow
) -> None:
    window.resize(900, 560)
    view = use(qapp, window, "timeline")
    window.findChild(QAbstractButton, "viewMonth").click()
    month_loaded(qapp, window)
    board = view.findChild(QWidget, "layoutMonthBoard")
    assert board is not None and board.isVisible()
    bar = board.scroll.verticalScrollBar()
    assert bar.maximum() > 0, "the month is taller than the window, so it scrolls"
    bar.setValue(0 if bar.value() else bar.maximum())
    chosen = bar.value()
    # A real change, saved: the design draws a new scene, as it does after any edit.
    window.session.add_block(
        {
            "id": "club",
            "title": "Club",
            "kind": "locked",
            "category": "extra",
            "start": "18:00",
            "duration_min": 60,
            "days": [5],
        }
    )
    window.session.save()
    settled(qapp, window)
    month_loaded(qapp, window)
    assert board.canvas.index_of(window.session.selected_day) is not None
    assert bar.value() == chosen


def test_a_chip_let_go_after_a_save_failed_is_refused_not_kept_for_later(
    qapp: QApplication, window: NativeWindow
) -> None:
    """A drop after a save that did not go through used to be parked in silence, overwritten by the
    next drop, and made much later when some other save finished."""
    session = window.session
    essay = session_of(window, "essay")
    thursday = date.fromisoformat(session.week_start) + timedelta(days=3)
    saturday = thursday + timedelta(days=2)
    session.pending_save = {"weeks": [], "assignments": [], "operation_id": "failed-before"}
    try:
        window._apply_change(MoveDate(essay["id"], thursday.isoformat(), saturday.isoformat()))
        assert window._date_waiting is None, "kept to be made later"
        assert "not saved yet" in session.message
    finally:
        session.pending_save = None
    settled(qapp, window)
    assert placed(window, "essay")[:2] == ([3], "19:00")


@pytest.mark.parametrize("design", ["classic", "timeline"])
def test_month_draws_a_week_left_unsaved_as_the_student_has_it(
    qapp: QApplication, window: NativeWindow, design: str
) -> None:
    """The essay moved to 20:15 and its week left without saving. Month showed it at 19:00, where the
    server has it, and a chip there could be picked up and then refused."""
    session = window.session
    essay = session_of(window, "essay")
    first = date.fromisoformat(session.week_start)
    thursday = (first + timedelta(days=3)).isoformat()
    assert session.hand_move(essay["id"], 3, 3, 20 * 60 + 15, 21 * 60 + 15) is True
    session.load_week((first + timedelta(days=7)).isoformat())
    wait_until(qapp, lambda: not session.busy and session.week_start != first.isoformat())
    assert not session.dirty, "the week now open has no changes; the one left behind has"
    if design == "classic":
        canvas = window.month_grid.canvas
    else:
        view = use(qapp, window, design)
    open_month_of(qapp, window, thursday)
    if design != "classic":
        board = view.findChild(QWidget, "layoutMonthBoard")
        assert board is not None and board.isVisible()
        canvas = board.canvas
    assert canvas.chip_words(essay["id"], thursday) == "8:15 PM History essay"
    window.session.preferences = {**(window.session.preferences or {}), "clock_24h": True}
    window._sync_chrome()
    spin(qapp, 5)
    assert canvas.chip_words(essay["id"], thursday) == "20:15 History essay"


def test_a_chip_from_a_week_that_is_not_open_is_judged_by_its_own_time_and_homework(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The essay is due on Sunday. With another week open, Month let its chip onto the Monday after,
    because the rule had no time or homework to judge it by."""
    session = window.session
    essay = session_of(window, "essay")
    first = date.fromisoformat(session.week_start)
    thursday = (first + timedelta(days=3)).isoformat()
    session.load_week((first + timedelta(days=7)).isoformat())
    wait_until(qapp, lambda: not session.busy and session.week_start != first.isoformat())
    open_month_of(qapp, window, thursday)
    late = window._date_judge(essay["id"], thursday, (first + timedelta(days=7)).isoformat())
    fine = window._date_judge(essay["id"], thursday, (first + timedelta(days=5)).isoformat())
    # The app's own words use contractions ("it's due").
    assert (late.ok, late.words) == (False, "That ends after it's due, so it stayed where it was.")
    assert (fine.ok, fine.words) == (True, "")
