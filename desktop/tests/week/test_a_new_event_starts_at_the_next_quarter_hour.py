"""A new event, Choose a time and Running late start at a time that is still ahead: the next quarter
hour, rounded up, never one that has passed."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")


from desktop.native.hours.geometry import next_slot
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.window_support import qapp  # noqa: F401


@pytest.mark.parametrize(
    ("now", "ahead", "slot"),
    [
        (0, 0, 0),
        (1, 0, 15),
        (15, 0, 15),
        (16 * 60 + 7, 0, 16 * 60 + 15),
        (23 * 60 + 33, 0, 23 * 60 + 45),
        (23 * 60 + 45, 0, 23 * 60 + 45),
        (23 * 60 + 46, 1, 0),
        (23 * 60 + 59, 1, 0),
    ],
)
def test_the_next_slot_is_the_next_quarter_hour_or_the_first_of_tomorrow(
    now: int, ahead: int, slot: int
) -> None:
    assert next_slot(now) == (ahead, slot)


def test_the_next_slot_keeps_to_the_hours_it_is_given() -> None:
    assert next_slot(3 * 60 + 10, first=6 * 60, last=23 * 60) == (0, 6 * 60), "not before the first"
    assert next_slot(23 * 60 + 1, first=6 * 60, last=23 * 60) == (1, 6 * 60), "none left: tomorrow's first"
    assert next_slot(22 * 60 + 50, first=6 * 60, last=23 * 60) == (0, 23 * 60)
