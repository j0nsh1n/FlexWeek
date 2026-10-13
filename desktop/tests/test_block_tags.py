"""Block pills: Overdue, Left from last week and Placed by Plan, in that order. No Short in 1.0.0 (N11)."""

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
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QFont, QImage, QPainter
    from PySide6.QtWidgets import QApplication

    from desktop.native.hours.canvas import BlockPainter, Drawn, block_tag_words, plan_placed
    from desktop.native.hours.geometry import Span
    from desktop.native.look import resolved_palette
    from desktop.native.weekmodel import Occurrence, length_label, range_label


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-block-tags-test"])


def occurrence(**changes: object) -> Occurrence:
    base = {
        "block_id": "math",
        "title": "Math worksheet",
        "category": "assignments",
        "day": 2,
        "start": 15 * 60,
        "end": 16 * 60,
        "work": True,
        "done": False,
        "missed": False,
        "assignment_id": "a1",
        "due": None,
        "slack": None,
    }
    return Occurrence(**{**base, **changes})


def test_a_thirty_minute_homework_block_is_not_tagged_short(qapp: QApplication) -> None:
    span = Span(2, 15 * 60, 15 * 60 + 30)
    drawn = Drawn("math", "Math worksheet", "assignments", True, span, 0, 1)
    assert block_tag_words(drawn) == ()
    assert "Short" not in drawn.detail
    assert drawn.detail == f"{range_label(span.start, span.end)} · {length_label(30)}"


def test_a_plan_placed_block_shows_placed_by_plan_at_the_end(qapp: QApplication) -> None:
    span = Span(2, 15 * 60, 16 * 60)
    drawn = Drawn("math", "Math worksheet", "assignments", True, span, 0, 1, placed_by_plan=True)
    assert block_tag_words(drawn) == ("Placed by Plan",)
    assert drawn.detail.endswith("Placed by Plan")


def test_tags_follow_overdue_then_placed_by_plan(qapp: QApplication) -> None:
    span = Span(2, 15 * 60, 16 * 60)
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
        placed_by_plan=True,
    )
    assert block_tag_words(drawn) == ("Overdue", "Placed by Plan")


@pytest.mark.parametrize(
    ("changes", "placed"),
    [
        ({}, True),
        ({"done": True}, False),
        ({"missed": True}, False),
        ({"pinned": True}, False),
        ({"work": False, "category": "class"}, False),
    ],
    ids=["unfinished-unpinned-homework", "finished", "missed", "pinned", "fixed-commitment"],
)
def test_only_unfinished_unpinned_homework_is_placed_by_plan(
    qapp: QApplication, changes: dict, placed: bool
) -> None:
    assert plan_placed(occurrence(**changes)) is placed


def test_a_design_that_writes_its_own_words_draws_no_pills_yet(qapp: QApplication) -> None:
    """The base painter lays out words it knows about; a design that writes its own (Clay, Retro,
    Bento, Mission) or has none (the one-thing bar) would draw a pill over them, so none of them does."""
    from desktop.native.layouts.bento import BentoPainter
    from desktop.native.layouts.clay import ClayPainter
    from desktop.native.layouts.mission import MissionPainter
    from desktop.native.layouts.one_thing import BarPainter
    from desktop.native.layouts.retro import RetroPainter

    for design in (BarPainter, BentoPainter, ClayPainter, MissionPainter, RetroPainter):
        assert design.draws_pills is False, design.__name__
    assert BlockPainter.draws_pills is True


def test_a_tag_is_drawn_only_when_the_time_line_stays_where_it_is(qapp: QApplication) -> None:
    """A one-hour block has no room for a pill above its words, so the pill goes to the tooltip and
    the time line stays put; a two-hour block keeps both."""
    palette = resolved_palette("system", False, None)
    painter = BlockPainter(palette, None)
    image = QImage(128, 200, QImage.Format.Format_ARGB32)
    image.fill(palette["window"])
    paint = QPainter(image)
    paint.setFont(QFont("Inter", 12))
    try:
        for minutes, shown in ((60, False), (120, True)):
            span = Span(2, 15 * 60, 15 * 60 + minutes)
            drawn = Drawn("math", "Math worksheet", "assignments", True, span, 0, 1, placed_by_plan=True)
            rect = QRectF(0, 0, 128, minutes * 48 / 60 - 3)
            visible = QRectF(0, 0, 128, 200)
            assert painter.pills_fit(paint.font(), rect, drawn, visible) is shown, minutes
    finally:
        paint.end()
