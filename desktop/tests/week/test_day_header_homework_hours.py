"""Each day's header says its hours of homework, whole at every width. How well they fit is a picture
(pictures/week_material.py, week.day-header-homework-length)."""

# ruff: noqa: F811
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")


from desktop.native.hours.scale import short_length
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.window_support import qapp  # noqa: F401


def test_a_short_homework_length_is_hours_and_minutes_not_a_time_of_day() -> None:
    """Friday's header at 810 px and Bento's day cards said "2 h 15", which reads like a time of day.
    The short form is "2h 15m" at every width."""
    assert short_length(135) == "2h 15m"
    assert short_length(90) == "1h 30m"
    assert short_length(60) == "1h"
    assert short_length(45) == "45 min"


