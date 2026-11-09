"""Each day's header says its hours of homework, whole at every width. How well they fit is a picture
(pictures/week_material.py, week.day-header-homework-length)."""

# ruff: noqa: F811
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QLabel

from desktop.native.hours.classic import DayName
from desktop.native.layouts.base import short_length
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.week.support_material import pump, seeded
from desktop.tests.window_support import qapp  # noqa: F401


def test_each_days_header_carries_its_homework_hours(qapp, window) -> None:
    """The "This week" card is gone; each day says its hours of homework under its date."""
    seeded(qapp, window)
    names = [window.week_table.findChild(QLabel, f"weekDayName{day}") for day in range(7)]
    assert [name.homework for name in names] == [60, 0, 0, 60, 0, 0, 0]
    assert names[3].property("today") is True and names[0].property("today") is False
    assert names[0].accessibleName().endswith("1 h of homework")


def test_a_days_homework_length_is_whole_or_the_short_form_at_every_window_width(qapp, window) -> None:
    seeded(qapp, window)
    label = window.week_table.findChild(QLabel, "weekDayName0")
    for width in range(810, 1281, 47):
        window.resize(width, 860)
        pump(qapp)
        label.show_day("Mon", "28", 90, False)
        words = label.homework_words()
        assert words in ("1 h 30 min", "1h 30m"), (width, words)


def test_a_short_homework_length_is_hours_and_minutes_not_a_time_of_day() -> None:
    """Friday's header at 810 px and Bento's day cards said "2 h 15", which reads like a time of day.
    The short form is "2h 15m" at every width."""
    assert short_length(135) == "2h 15m"
    assert short_length(90) == "1h 30m"
    assert short_length(60) == "1h"
    assert short_length(45) == "45 min"


def test_fridays_header_says_2h_15m_when_the_column_is_narrow(qapp) -> None:
    """The day's homework length under Friday must not look like 2:15, including a Friday column as
    wide as it is in an 810 px window."""
    name = DayName(4)
    name.show_day("Fri", "18", 135, False)
    for width in (48, 77, 96, 120):
        name.resize(width, 80)
        words = name.homework_words()
        assert words == "2h 15m", (width, words)
        assert ":" not in words
        assert words != "2 h 15"
