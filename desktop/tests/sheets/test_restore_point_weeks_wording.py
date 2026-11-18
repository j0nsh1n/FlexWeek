"""A restore point says "1 week" for one week and "N weeks" otherwise (the row both looks share)."""

from __future__ import annotations

import pytest

from desktop.native.settings_copy import restore_parts, restore_row

CASES = [(0, "0 weeks"), (1, "1 week"), (2, "2 weeks"), (12, "12 weeks")]


@pytest.mark.parametrize(("count", "words"), CASES)
def test_the_week_count_is_singular_only_for_one(count: int, words: str) -> None:
    point = {"label": "Before import", "created_at": "2026-11-01 09:00", "weeks_count": count}
    assert restore_parts(point) == ("Before import", f"2026-11-01 09:00 · {words}")
    assert restore_row(point) == f"Before import · 2026-11-01 09:00 · {words}"
