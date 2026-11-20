# ruff: noqa: F811
# Fixtures are imported by name, so a test taking one as an argument redefines it.
"""The first homework's due date starts on the next school day after today."""

from __future__ import annotations

from datetime import date

import pytest

pytest.importorskip("PySide6")


from desktop.native.setup_steps import next_school_day
from desktop.tests.window_support import qapp  # noqa: F401


def test_the_next_school_day_is_after_today_and_on_a_school_day() -> None:
    assert next_school_day([], date(2026, 10, 3)) == "2026-10-04", "no school days: tomorrow"
    # Saturday 3 October 2026: the next of Monday to Friday is Monday the 5th.
    assert next_school_day([0, 1, 2, 3, 4], date(2026, 10, 3)) == "2026-10-05"
    assert next_school_day([4], date(2026, 10, 2)) == "2026-10-09", "after today, not today"
