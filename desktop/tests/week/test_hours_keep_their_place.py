"""Where the hours are scrolled to when they open, are laid out again, lose their room for a moment, or
are shown again after being hidden. Clay's cards slide in beside the open one, so a page can give the
hours no width at all for a moment; where the student left them must survive that."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.weekmodel import build_week  # noqa: E402
from desktop.tests.week import support_zoom  # noqa: E402
from desktop.tests.week.support_zoom import (  # noqa: E402
    MONDAY,
    NOW,
    SCHOOL,
    a_week,
    hours_placed_by_hand,
    minute_at,
    settle,
)

qapp = support_zoom.qapp  # a fixture is found by its name in the test module


def middle_minute(view) -> float:
    top, bottom = minute_at(view, 0), minute_at(view, view.scroll.viewport().height())
    return (top + bottom) / 2


def test_hours_that_grow_twice_while_opening_still_open_where_they_were_asked(qapp: QApplication) -> None:
    """A page still laying out can show the hours taller than they end up, twice over. The bar stops
    short of 10:00 each time it is pulled back by the growing hours; that is not the student
    scrolling, so once the hours are their own height they start at 10:00."""
    view = a_week(qapp)
    view.resize(760, 900)
    settle(qapp)
    view.scroll.scroll_to(10 * 60, above=0)
    settle(qapp)
    view.resize(760, 1100)
    settle(qapp)
    view.resize(760, 520)
    settle(qapp)
    at = minute_at(view, 0)
    assert 9 * 60 + 45 <= at <= 10 * 60 + 15, f"the hours start at {int(at) // 60:02d}:{int(at) % 60:02d}"


def test_a_week_keeps_where_it_was_scrolled_when_it_is_shown_again(qapp: QApplication) -> None:
    view = a_week(qapp)
    bar = view.scroll.verticalScrollBar()
    view.set_week(build_week("2026-09-28", [], {}, None), None, None)
    opened_at = bar.value()
    bar.setValue(bar.maximum())
    view.hide()
    view.set_week(build_week("2026-09-28", [SCHOOL], {}, None), None, None)
    view.show()
    settle(qapp)
    assert opened_at != bar.maximum()
    assert bar.value() == bar.maximum(), "the same week jumped back to the morning"
    view.hide()
    other = build_week("2026-10-05", [], {}, None)
    view.set_week(other, 2, 12 * 60)
    view.set_week(other, 2, 12 * 60)
    view.show()
    settle(qapp)
    assert abs(middle_minute(view) - 12 * 60) <= 2, "a hidden refresh lost the opening time"


def test_the_same_week_rendered_again_keeps_now_in_the_middle_while_the_page_settles(
    qapp: QApplication,
) -> None:
    """A save or a tick of the clock renders the week again. Opened with now in the middle, it keeps now
    there as the page settles, as a new look's taller header makes it, until the student scrolls."""
    view = a_week(qapp)
    view.set_week(build_week(MONDAY, [], {}, None), 3, NOW + 1)
    view.resize(760, 640)
    settle(qapp)
    assert abs(middle_minute(view) - NOW) <= 2


def test_hours_cut_short_for_a_moment_go_back_to_where_they_were(qapp: QApplication) -> None:
    """A page laying itself out can give the hours a little less to scroll for a moment. The bar is
    cut back to that end, and once the room returns the hours are where the student left them."""
    view = a_week(qapp)
    bar = view.scroll.verticalScrollBar()
    bar.setValue(bar.maximum())
    end = bar.value()
    view.resize(760, 560)
    settle(qapp)
    assert bar.value() < end, "taller for a moment, the hours had less to scroll"
    view.resize(760, 520)
    settle(qapp)
    assert bar.value() == end


def test_y_for_is_safe_when_the_canvas_has_no_tracks(qapp: QApplication) -> None:
    """Clay's card slide can leave a kept centre while `_lay_out_now` clears the tracks; `_y_for` must
    not index an empty list (often seen as IndexError from `viewportEvent`)."""
    view = hours_placed_by_hand(qapp)
    scroll = view.scroll
    scroll.setGeometry(0, 0, 40, 520)
    settle(qapp)
    assert not scroll.canvas.tracks
    assert scroll._y_for(8 * 60) == 0.0

    scroll.setGeometry(0, 0, 760, 520)
    settle(qapp)
    scroll.scroll_to(10 * 60)
    bar = scroll.verticalScrollBar()
    scroll._placed = bar.value()
    scroll.setGeometry(0, 0, 40, 520)
    if scroll.canvas.tracks:
        scroll._keep_centre()
    QApplication.sendEvent(scroll.viewport(), QEvent(QEvent.Type.Resize))
    settle(qapp)


def test_a_time_asked_for_while_the_hours_have_no_room_is_shown_once_they_do(qapp: QApplication) -> None:
    """Clay deck's open card slides in from a narrow neighbour, and for a moment its hours have no width
    at all. A time asked for then waited for the hours to be shown again, which never came, and the
    day opened at the wrong hour."""
    view = a_week(qapp)
    scroll = view.scroll
    view.layout().removeWidget(scroll)
    scroll.setGeometry(0, 0, 760, 520)
    scroll.scroll_to(8 * 60, above=0)
    settle(qapp)
    scroll.setGeometry(0, 0, 40, 520)
    settle(qapp)
    assert not view.hours.tracks, "no room for the hours"
    scroll.scroll_to(11 * 60, above=0)
    scroll.setGeometry(0, 0, 760, 520)
    settle(qapp)
    assert abs(minute_at(view, 0) - 11 * 60) <= 1


def test_a_week_left_while_its_hours_have_no_room_is_where_it_was_when_it_is_shown_again(
    qapp: QApplication,
) -> None:
    """Clay deck's card for another day slides in with no width for its hours, and the day being left
    is only then told apart from the new one. Where it was scrolled to is still remembered."""
    view = hours_placed_by_hand(qapp)
    scroll = view.scroll
    scroll.scroll_to(5 * 60, above=0)
    assert abs(minute_at(view, 0) - 5 * 60) <= 1
    scroll.setGeometry(0, 0, 40, 520)
    settle(qapp)
    assert not view.hours.tracks, "no room for the hours"
    view.set_week(build_week("2026-09-28", [], {}, None), None, None)
    scroll.setGeometry(0, 0, 760, 520)
    settle(qapp)
    assert abs(minute_at(view, 0) - (8 * 60 - 90)) <= 1, "an empty week opens an hour and a half above 08:00"
    view.set_week(build_week(MONDAY, [], {}, None), 3, NOW)
    settle(qapp)
    assert abs(minute_at(view, 0) - 5 * 60) <= 1


def test_a_week_gone_back_to_while_its_hours_have_no_room_is_put_where_it_was_once_they_do(
    qapp: QApplication,
) -> None:
    view = hours_placed_by_hand(qapp)
    scroll = view.scroll
    scroll.scroll_to(5 * 60, above=0)
    view.set_week(build_week("2026-09-28", [], {}, None), None, None)
    settle(qapp)
    assert abs(minute_at(view, 0) - (8 * 60 - 90)) <= 1
    scroll.setGeometry(0, 0, 40, 520)
    settle(qapp)
    assert not view.hours.tracks, "no room for the hours"
    view.set_week(build_week(MONDAY, [], {}, None), 3, NOW)
    scroll.setGeometry(0, 0, 760, 520)
    settle(qapp)
    assert abs(minute_at(view, 0) - 5 * 60) <= 1


def test_a_week_scrolled_while_its_hours_waited_for_room_is_left_where_it_was_scrolled_to(
    qapp: QApplication,
) -> None:
    """Hours cut short keep where they were until the room returns. Scrolled meanwhile, that is where
    the student left them, not the place they were waiting to go back to."""
    view = a_week(qapp)
    bar = view.scroll.verticalScrollBar()
    bar.setValue(bar.maximum())
    view.resize(760, 560)
    settle(qapp)
    bar.setValue(bar.value() - 40)
    left = minute_at(view, 0)
    view.set_week(build_week("2026-09-28", [], {}, None), None, None)
    settle(qapp)
    assert abs(minute_at(view, 0) - (8 * 60 - 90)) <= 1
    view.set_week(build_week(MONDAY, [], {}, None), 3, NOW)
    settle(qapp)
    assert abs(minute_at(view, 0) - left) <= 1


def test_a_week_asked_for_and_never_shown_has_no_place_to_go_back_to(qapp: QApplication) -> None:
    """Day's hours are given every day the student picks while Week is on screen. A day they never saw
    opens as a first sight of it does, not wherever the hidden hours happened to lie."""
    view = a_week(qapp)
    view.hide()
    unseen = build_week("2026-09-28", [], {}, None)
    view.set_week(unseen, 2, 12 * 60)
    view.set_week(build_week("2026-10-05", [], {}, None), None, None)
    view.set_week(unseen, 2, 12 * 60)
    view.show()
    settle(qapp)
    assert abs(middle_minute(view) - 12 * 60) <= 2


def test_a_week_opened_while_hidden_scrolls_to_now_when_it_is_shown(qapp: QApplication) -> None:
    view = a_week(qapp)
    view.hide()
    view.scroll.verticalScrollBar().setValue(0)
    view.set_week(build_week("2026-10-05", [], {}, None), 2, 12 * 60)
    view.show()
    settle(qapp)
    assert abs(middle_minute(view) - 12 * 60) <= 2, "a new week opens with now in the middle"
