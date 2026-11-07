"""After a plan the blocks slide to their places and new ones fade in; under Reduce they only fade; a
block let go by hand is already where it belongs."""

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
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication

    from desktop.native.motion import EASE_MS, apply_ui_effects, duration
    from desktop.tests.motion_support import ManualTime, manual_time  # noqa: F401
    from desktop.tests.settings.support_motion import LATER, Hours, occurrence
    from desktop.tests.window_support import qapp  # noqa: F401


@pytest.fixture(autouse=True)
def motion_is_put_back() -> Iterator[None]:
    apply_ui_effects("normal")
    yield
    apply_ui_effects("normal")


def test_after_a_plan_blocks_slide_to_their_places_and_new_ones_fade_in(
    qapp: QApplication, manual_time: ManualTime  # noqa: F811
) -> None:
    apply_ui_effects("normal")
    hours = Hours(qapp)
    final = hours.settled_picture(LATER)
    hours.canvas.set_week(LATER)
    manual_time.advance(40)
    # 40 of the 220 ms planning ease on the out-cubic curve: 1 - (1 - 2/11)^3.
    assert hours.canvas._progress == pytest.approx(1 - (9 / 11) ** 3)
    assert hours.picture() != final, "partway there, not already there"
    manual_time.advance(duration(EASE_MS) - 40)
    assert hours.picture() == final
    hours.window.close()


def first_frame_and_last(qapp: QApplication, level: str) -> tuple[QImage, QImage, QPoint]:  # noqa: F811
    """The hours the moment a plan moved the essay from Tuesday 9:00, as they end up, and where the
    essay was."""
    apply_ui_effects(level)
    hours = Hours(qapp)
    was = hours.canvas.tracks[1].rect_for(9 * 60, 10 * 60).center().toPoint()
    final = hours.settled_picture(LATER)
    hours.canvas.set_week(LATER)
    first = hours.picture()
    hours.window.close()
    return first, final, was


def test_under_reduce_a_moved_block_fades_in_where_it_went_rather_than_sliding(qapp: QApplication) -> None:  # noqa: F811
    """The motion-sensitive student: fades yes, sliding blocks no."""
    first, final, was = first_frame_and_last(qapp, "normal")
    assert first.pixelColor(was) != final.pixelColor(was), "Normal starts it where it was"
    first, final, was = first_frame_and_last(qapp, "reduce")
    assert first.pixelColor(was) == final.pixelColor(was), "Reduce never draws it there"
    assert first != final, "but it still fades in"


def test_laying_the_hours_out_again_where_nothing_moved_keeps_the_slide(
    qapp: QApplication, manual_time: ManualTime  # noqa: F811
) -> None:
    """After Plan the hours scroll to what it placed, and the slide was cut short by that scroll's
    layout, so nothing was seen to move."""
    hours = Hours(qapp)
    final = hours.settled_picture(LATER)
    hours.canvas.set_week(LATER)
    hours.canvas.relayout()
    manual_time.advance(40)
    assert hours.picture() != final, "still on its way"
    manual_time.advance(duration(EASE_MS) - 40)
    assert hours.picture() == final
    hours.window.close()


def test_a_block_let_go_by_hand_is_already_where_it_belongs(qapp: QApplication) -> None:  # noqa: F811
    hours = Hours(qapp)
    moved = [occurrence("essay", 3, 15 * 60, 16 * 60)]
    final = hours.settled_picture(moved)
    hours.hand.dropped = "essay"
    hours.canvas.set_week(moved)
    assert hours.picture() == final, "it does not jump back to slide from where it was picked up"
    hours.window.close()
