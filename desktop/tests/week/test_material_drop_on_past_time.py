"""Dropping a drawer card on a time that has already passed says why in the snackbar, in the words the app
uses for a past time, and moves nothing. The one clock reads Thursday 19:00."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import timedelta

from desktop.tests.week.support_material import (
    NOW_DAY,
    _bridge,
    _homework,
    _pref,
    _pump,
    _reset,
    _snack,
    _week_monday,
    material_window,  # noqa: F401
)
from desktop.tests.window_support import qapp, settled  # noqa: F401

# _reset puts the clock on 24-hour.
PAST = "That time has passed. Choose 19:00 or later today, or another day."


def waiting_card(window) -> dict:
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, "math", "Math worksheet", 30, due)
    return next(b for b in window.session.blocks if b.get("assignment_id") == "math")


def test_dropping_a_card_on_a_past_time_says_why_and_places_nothing(qapp, window) -> None:
    _reset(window, qapp)
    card = waiting_card(window)
    _bridge(window).week.placeHomework(card["id"], NOW_DAY, 16 * 60 + 45)
    settled(qapp, window)
    _pump(qapp)
    assert _snack(window) == PAST
    again = next(b for b in window.session.blocks if b["id"] == card["id"])
    assert not again.get("start"), "the card stayed in the drawer"


def test_dropping_a_card_on_a_time_still_ahead_places_it(qapp, window) -> None:
    _reset(window, qapp)
    card = waiting_card(window)
    _bridge(window).week.placeHomework(card["id"], NOW_DAY, 21 * 60)
    settled(qapp, window)
    _pump(qapp)
    again = next(b for b in window.session.blocks if b["id"] == card["id"])
    assert again["start"] == "21:00"
    assert _snack(window) != PAST


def _drop_on_step(qapp, window, step: int, minute: int) -> dict:
    _reset(window, qapp)
    _pref(window, drag_step_min=step)
    window._material_page.publish()
    _pump(qapp)
    card = waiting_card(window)
    _bridge(window).week.placeHomework(card["id"], NOW_DAY, minute)
    settled(qapp, window)
    _pump(qapp)
    return next(b for b in window.session.blocks if b["id"] == card["id"])


def test_a_drop_that_snaps_up_to_now_is_placed(qapp, window) -> None:
    # 18:53 is past, but on a 15-minute step the card takes 19:00, which is now.
    again = _drop_on_step(qapp, window, 15, 18 * 60 + 53)
    assert again["start"] == "19:00"
    assert _snack(window) != PAST


def test_a_drop_that_snaps_down_into_the_past_is_refused(qapp, window) -> None:
    # 18:52 snaps to 18:45, a time that has passed: judged on the time the card would take.
    again = _drop_on_step(qapp, window, 15, 18 * 60 + 52)
    assert _snack(window) == PAST
    assert not again.get("start")
    assert str(_bridge(window).property("snackAction")) == ""
