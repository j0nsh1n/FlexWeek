# ruff: noqa: F811
"""Homework due tonight that has no time yet is named on every main view and day screen, and none of them
says the day is free."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from backend.tests.fake_clock import CLOCK  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    qapp,  # noqa: F401
    settled,
    thursday_at,
    visible_copy,
    window,  # noqa: F401
)

FREE_TODAY = (
    "done for today",
    "nothing else today",
    "all clear",
    "the rest of the day is yours",
    "a free day",
    "0 min left today",
    "nothing on this day",
    "no homework tonight",
)

SCREENS = (
    ("classic", "week"),
    ("timeline", "week"),
    ("mission", "week"),
    ("bento", "week"),
    ("retro", "week"),
    ("clay", "week"),
    ("one", "day"),
    ("dial", "day"),
)


@pytest.mark.parametrize(("layout_id", "surface"), SCREENS)
def test_unplaced_homework_due_today_is_named_on_every_screen(
    qapp: QApplication, window: NativeWindow, layout_id: str, surface: str
) -> None:
    """Math worksheet due tonight with no time. No screen may say the day is free, and each names it."""
    session = window.session
    CLOCK.set(thursday_at(window, 16))
    session.blocks = [item for item in session.blocks if item.get("assignment_id") != "essay"]
    session._touch("clearing the placed essay")
    due = f"{thursday_at(window, 0).date().isoformat()}T21:00"
    session.add_homework(
        {
            "id": "math",
            "title": "Math worksheet",
            "due": due,
            "estimate_min": 45,
            "revision": 0,
        }
    )
    session.save()
    settled(qapp, window)
    if surface == "day":
        window._layout = {"main": "classic", "day": layout_id, "options": {}}
        window._day_mode = True
    else:
        window._layout = {"main": layout_id, "day": "one", "options": {}}
        window._day_mode = False
        session.set_view("week")
    window._on_week()
    qapp.processEvents()
    said = visible_copy(window).lower()
    if layout_id == "dial":
        # The demo's not-placed strip on the day dial gives the count only; the names are not listed.
        assert "1 homework not placed yet" in said, said
        assert "math worksheet" not in said, said
    else:
        assert "math worksheet" in said, said
    for phrase in FREE_TODAY:
        assert phrase not in said, f"{layout_id} still says {phrase!r} in:\n{said}"
