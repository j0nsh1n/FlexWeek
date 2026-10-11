"""A 12-hour range that ends at midnight keeps the AM/PM of its start (0.19.2, T-W1).

"9 AM–12 AM" must never print as "9–12 AM". The words come from one engine function, `range_label`;
the callers are checked to use it rather than their own join.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from desktop.native.hours.canvas import Drawn
from desktop.native.hours.geometry import Span
from desktop.native.weekmodel import range_label, set_clock_24h

NATIVE = Path(__file__).resolve().parents[1] / "native"
# Every place the range of a block is written; the week list reads it through Drawn.detail.
CALLERS = ("hours/canvas.py", "layouts/one_thing.py", "layouts/dial.py", "layouts/mission.py")
CLOCK_WORDS = {"clock_label", "clock_text", "short_clock", "hhmm_text"}


@pytest.fixture()
def twelve():
    set_clock_24h(False)
    yield
    set_clock_24h(True)


@pytest.mark.parametrize(
    ("start", "end", "words"),
    [
        (9 * 60, 24 * 60, "9 AM–12 AM"),
        (9 * 60, 0, "9 AM–12 AM"),
        (23 * 60, 24 * 60, "11 PM–12 AM"),
        (11 * 60 + 30, 24 * 60, "11:30 AM–12 AM"),
        (16 * 60, 17 * 60 + 30, "4–5:30 PM"),
        (9 * 60, 11 * 60, "9–11 AM"),
    ],
)
def test_a_range_names_both_marks_when_it_ends_at_midnight(twelve, start: int, end: int, words: str) -> None:
    assert range_label(start, end) == words


def test_the_24_hour_clock_is_unchanged() -> None:
    set_clock_24h(True)
    assert range_label(9 * 60, 24 * 60) == "09:00–24:00"


def test_a_block_ending_at_midnight_says_it_on_the_hours_and_in_the_week_list(twelve) -> None:
    drawn = Drawn("late", "Late shift", "work", False, Span(2, 9 * 60, 24 * 60), 0, 1)
    assert drawn.times == "9 AM–12 AM"
    assert drawn.detail.startswith("9 AM–12 AM · ")


@pytest.mark.parametrize("path", CALLERS)
def test_each_caller_writes_ranges_with_range_label(path: str) -> None:
    tree = ast.parse((NATIVE / path).read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "range_label"
    ]
    assert calls, f"{path} no longer calls range_label"
    for node in ast.walk(tree):
        if not isinstance(node, ast.JoinedStr):
            continue
        for index, part in enumerate(node.values):
            if not (isinstance(part, ast.Constant) and "–" in str(part.value)):
                continue
            around = node.values[max(index - 1, 0) : index + 2]
            written = {
                side.value.func.id
                for side in around
                if isinstance(side, ast.FormattedValue)
                and isinstance(side.value, ast.Call)
                and isinstance(side.value.func, ast.Name)
            }
            assert not written & CLOCK_WORDS, f"{path}:{node.lineno} joins two times itself"
