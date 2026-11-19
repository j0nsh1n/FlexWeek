"""Dragging in every design, not only Today's app: homework and blocks put down at a time, by one rule
and in the same words everywhere, through the window's one hand.
"""

# ruff: noqa: E402, F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native.hours.geometry import Span
from desktop.native.hours.hand import Place
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.week.support_design_plan import (
    SIZE,
    placed,
    plan_week,
    session_of,
    settled,
)
from desktop.tests.window_support import qapp  # noqa: F401


@pytest.fixture()
def window(qapp: QApplication, open_light: Callable[..., NativeWindow]) -> NativeWindow:
    """This week: School Monday to Friday 08:00-14:30, the History essay on Thursday 19:00-20:00, and
    a Math worksheet that still needs a time. The clock is held at Thursday 10:00."""
    return plan_week(qapp, open_light(SIZE))




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


