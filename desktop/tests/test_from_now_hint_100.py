"""The "Today from ... onward." hint rounds the clock up to the next quarter hour, as the past-time sentence
does, with no 6:00 AM floor (1.0.0 decision on the past-time sentence)."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from desktop.native.weekmodel import clock_text
from desktop.native.widgets import today_from_words


def test_the_hint_names_the_next_quarter_hour_from_now() -> None:
    # The clock style is the app's own (clock_text); the rule under test is which quarter hour.
    assert today_from_words(15 * 60 + 7) == f"Today from {clock_text(15 * 60 + 15)} onward."
    assert today_from_words(15 * 60 + 15) == f"Today from {clock_text(15 * 60 + 15)} onward."


def test_the_hint_has_no_6_am_floor() -> None:
    assert today_from_words(5 * 60 + 10) == f"Today from {clock_text(5 * 60 + 15)} onward."


def test_the_hint_says_nothing_once_the_day_has_no_quarter_hour_left() -> None:
    assert today_from_words(23 * 60 + 50) == ""
