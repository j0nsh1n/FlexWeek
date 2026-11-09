"""A short block must still move when it is pressed, and an hour still resizes from its edges, at every
zoom level."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QPointF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.hours.classic import DAY_SCALE, WEEK_SCALE, ClassicDay, ClassicWeek  # noqa: E402
from desktop.native.hours.hand import Gesture  # noqa: E402
from desktop.tests.week import support_zoom  # noqa: E402
from desktop.tests.week.support_zoom import QUARTER, a_day, a_week, press_and_drag, settle  # noqa: E402

qapp = support_zoom.qapp  # a fixture is found by its name in the test module


def press_kind(view: ClassicWeek | ClassicDay, block_id: str, day: int, share: float) -> Gesture:
    """What pressing a drawn block this far along it and moving a little picks up."""
    rect = view.hours.block_rect(block_id, day)
    assert rect is not None, f"{block_id} is not drawn"
    at = QPoint(rect.center().x(), rect.top() + round(rect.height() * share))
    press_and_drag(view.hours, QPointF(view.hours.mapFromGlobal(at)), QPointF(0, 12))
    preview = view.hours.hand.preview
    view.hours.hand.cancel()
    assert preview is not None, f"pressing {share:.0%} into {block_id} picked nothing up"
    return preview.held.kind


@pytest.mark.parametrize("px", WEEK_SCALE.levels)
def test_a_quarter_hour_on_the_week_moves_from_a_quarter_half_and_three_quarters_in(
    qapp: QApplication, px: int
) -> None:
    view = a_week(qapp, [QUARTER])
    view.scroll.restore({"classic.week": px})
    view.scroll.scroll_to(16 * 60)
    settle(qapp)
    for share in (0.25, 0.5, 0.75):
        assert press_kind(view, "quiz", 3, share) is Gesture.MOVE, f"{share:.0%} at {px} px an hour"


@pytest.mark.parametrize("px", DAY_SCALE.levels)
def test_a_quarter_hour_on_the_day_moves_from_a_quarter_half_and_three_quarters_in(
    qapp: QApplication, px: int
) -> None:
    view = a_day(qapp, [QUARTER], 3)
    view.scroll.restore({"classic.day": px})
    view.scroll.scroll_to(16 * 60)
    settle(qapp)
    for share in (0.25, 0.5, 0.75):
        assert press_kind(view, "quiz", 3, share) is Gesture.MOVE, f"{share:.0%} at {px} px an hour"


def test_an_hour_still_resizes_from_its_edges_at_every_level(qapp: QApplication) -> None:
    hour = {**QUARTER, "duration_min": 60}
    view = a_day(qapp, [hour], 3)
    for px in DAY_SCALE.levels:
        view.scroll.restore({"classic.day": px})
        view.scroll.scroll_to(16 * 60)
        settle(qapp)
        assert press_kind(view, "quiz", 3, 0.02) is Gesture.RESIZE_START, f"top edge at {px}"
        assert press_kind(view, "quiz", 3, 0.97) is Gesture.RESIZE_END, f"bottom edge at {px}"
