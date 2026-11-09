"""Dropping a drawer card on a time that has already passed says why in the snackbar, in the words the app
uses for a past time, and moves nothing. The one clock reads Thursday 19:00."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import timedelta

from desktop.tests.week.support_material import (
    NOW_DAY,
    _bridge,
    _homework,
    _pump,
    _reset,
    _snack,
    _week_monday,
    material_window,  # noqa: F401
)
from desktop.tests.window_support import qapp, settled  # noqa: F401

PAST = "That time has passed. Choose 19:00 or later today, or another day."  # _reset puts the clock on 24-hour


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
