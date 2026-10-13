"""Block pills: Short and Placed by Plan, in order with Overdue and Left from last week."""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtWidgets import QApplication

    from desktop.native.hours.canvas import Drawn, block_tag_words
    from desktop.native.hours.geometry import Span
    from desktop.native.weekmodel import length_label, range_label


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-block-tags-test"])


def test_a_hand_shrunk_block_ends_its_accessible_detail_with_short_30_min(qapp: QApplication) -> None:
    span = Span(2, 15 * 60, 15 * 60 + 30)
    drawn = Drawn(
        "math",
        "Math worksheet",
        "assignments",
        True,
        span,
        0,
        1,
        estimate_min=60,
    )
    assert block_tag_words(drawn) == ("Short 30 min",)
    assert drawn.detail.endswith("Short 30 min")
    assert drawn.detail.startswith(f"{range_label(span.start, span.end)} · {length_label(30)}")


def test_a_plan_placed_block_shows_placed_by_plan_not_short(qapp: QApplication) -> None:
    span = Span(2, 15 * 60, 16 * 60)
    drawn = Drawn(
        "math",
        "Math worksheet",
        "assignments",
        True,
        span,
        0,
        1,
        estimate_min=60,
        placed_by_plan=True,
    )
    assert block_tag_words(drawn) == ("Placed by Plan",)
    assert "Short" not in drawn.detail
    assert drawn.detail.endswith("Placed by Plan")


def test_tags_follow_overdue_short_left_then_placed_by_plan(qapp: QApplication) -> None:
    span = Span(2, 15 * 60, 15 * 60 + 30)
    drawn = Drawn(
        "bio",
        "Bio reading",
        "assignments",
        True,
        span,
        0,
        1,
        history="Overdue",
        history_due="2026-10-03T23:59",
        estimate_min=60,
        placed_by_plan=True,
    )
    assert block_tag_words(drawn) == ("Overdue", "Short 30 min", "Placed by Plan")
