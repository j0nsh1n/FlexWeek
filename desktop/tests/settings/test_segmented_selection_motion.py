"""The view control's chosen pill slides to the segment chosen; where things may not travel it fades
across, and with animations off it is simply there. Read from the pill rectangles the track draws,
not from pixels (how the pill looks is the pictures')."""

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
    from PySide6.QtCore import QAbstractAnimation, QRectF
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QApplication, QHBoxLayout

    from desktop.native.motion import SEGMENT_MS, apply_ui_effects, duration
    from desktop.native.widgets import Segment, SegmentTrack
    from desktop.tests.motion_support import ManualTime, manual_time  # noqa: F401
    from desktop.tests.settings.support_motion import move_on
    from desktop.tests.window_support import qapp  # noqa: F401


@pytest.fixture(autouse=True)
def motion_is_put_back() -> Iterator[None]:
    apply_ui_effects("normal")
    yield
    apply_ui_effects("normal")


def segments(qapp: QApplication) -> tuple[SegmentTrack, list[Segment]]:  # noqa: F811
    track = SegmentTrack()
    track.setLayout(QHBoxLayout())
    track.layout().setContentsMargins(0, 0, 0, 0)
    colours = track.palette()
    colours.setColor(QPalette.ColorRole.AlternateBase, QColor("#ffffff"))
    colours.setColor(QPalette.ColorRole.WindowText, QColor("#ffffff"))
    colours.setColor(QPalette.ColorRole.Highlight, QColor("#ff0000"))
    track.setPalette(colours)
    made = []
    for words in ("Day", "Week", "Month"):
        button = Segment(words)
        button.setCheckable(True)
        button.setStyleSheet("background: transparent; border: none; color: #ffffff;")
        track.add(button)
        made.append(button)
    made[0].setChecked(True)
    track.show()
    qapp.processEvents()
    # Drawn once, so the track knows where the chosen pill is.
    track.grab()
    return track, made


def test_the_chosen_pill_slides_over_the_segments_between_to_the_one_chosen(
    qapp: QApplication, manual_time: ManualTime  # noqa: F811
) -> None:
    """The view control's selection used to jump."""
    apply_ui_effects("normal")
    track, (day, week, month) = segments(qapp)
    start, target = QRectF(day.geometry()), QRectF(month.geometry())
    month.setChecked(True)
    assert track._pills(target) == [(start, 1.0)], "it leaves from where it was"
    # A fifth of the way through, where the out-cubic curve is 1 - (4/5)^3 of the way.
    manual_time.advance(duration(SEGMENT_MS) // 5)
    ((pill, opacity),) = track._pills(target)
    share = 1 - (4 / 5) ** 3
    assert opacity == 1.0
    assert pill.x() == pytest.approx(start.x() + (target.x() - start.x()) * share)
    assert pill.intersects(QRectF(week.geometry())), "and passes over the segment between, as no fade would"
    move_on(manual_time, duration(SEGMENT_MS) + 150)
    assert track._pills(target) == [(target, 1.0)]
    track.close()


def test_under_reduce_the_chosen_pill_fades_across_instead_of_travelling(
    qapp: QApplication, manual_time: ManualTime  # noqa: F811
) -> None:
    apply_ui_effects("reduce")
    track, (day, _week, month) = segments(qapp)
    start, target = QRectF(day.geometry()), QRectF(month.geometry())
    month.setChecked(True)
    manual_time.advance(duration(SEGMENT_MS) // 5)
    share = 1 - (4 / 5) ** 3
    leaving, arriving = track._pills(target)
    assert leaving == (start, pytest.approx(1 - share)), "the old pill stays where it was, fading out"
    assert arriving == (target, pytest.approx(share)), "the new one fades in where it will be"
    track.close()


def test_with_animations_off_the_chosen_pill_is_simply_there(qapp: QApplication) -> None:  # noqa: F811
    apply_ui_effects("off")
    track, (day, _week, month) = segments(qapp)
    month.setChecked(True)
    assert track._slide.state() == QAbstractAnimation.State.Stopped, "no slide starts"
    assert track._pills(QRectF(month.geometry())) == [(QRectF(month.geometry()), 1.0)]
    day.setChecked(True)
    assert track._slide.state() == QAbstractAnimation.State.Stopped
    assert track._pills(QRectF(day.geometry())) == [(QRectF(day.geometry()), 1.0)]
    track.close()
