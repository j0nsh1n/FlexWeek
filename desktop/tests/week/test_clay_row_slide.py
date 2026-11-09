"""Clay deck's row sliding on Week: how long it slides at each motion level, that its cards are not
repainted on every frame, what the pictures that slide are doing and where the live hours stay."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QAbstractAnimation, QEvent, QObject  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget  # noqa: E402

from desktop.native import motion  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.week.support_clay import (  # noqa: E402, F401
    front,
    landed,
    shown,
    slide_pictures,
    slide_week,
    still,
    stop_slide,
    takeover_between_the_pictures,
)


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-clay-test"])
    yield application


def test_a_sliding_row_does_not_repaint_its_cards_every_frame(qapp: QApplication) -> None:
    """The row slides a picture of its cards. The cards themselves stay unpainted until it lands."""

    class Count(QObject):
        def __init__(self) -> None:
            super().__init__()
            self.paints = 0

        def eventFilter(self, _watched: QObject, event: QEvent) -> bool:  # noqa: N802
            if event.type() == QEvent.Type.Paint:
                self.paints += 1
            return False

    view = shown(qapp)
    motion.apply_ui_effects("normal")
    cards = []
    for day in range(7):
        canvas = view.row.findChild(QWidget, f"clayPeek{day}")
        assert canvas is not None
        cards.append(canvas.parentWidget())
    counter = Count()
    for card in cards:
        card.installEventFilter(counter)
    view.findChild(QPushButton, "clayAhead").click()
    assert view.row._slide.state() == QAbstractAnimation.State.Running
    counter.paints = 0
    frames = 0
    during_the_slide = 0

    def landed_yet() -> bool:
        nonlocal frames, during_the_slide
        if view.row._slide.state() == QAbstractAnimation.State.Running:
            frames += 1
            during_the_slide = counter.paints
            return False
        return True

    wait_until(qapp, landed_yet, what="the row finishing its slide")
    assert frames > 0, "the row slid for at least a frame"
    assert during_the_slide <= 3, f"the cards painted {during_the_slide} times over {frames} frames"
    assert view.row.front == 4
    thursday = view.row.findChild(QWidget, "clayPeek3").parentWidget()
    assert thursday.isVisible()


def test_the_row_slides_when_motion_is_on_and_jumps_with_motion_off(qapp: QApplication) -> None:
    view = shown(qapp)
    motion.apply_ui_effects("normal")
    friday = view.row.findChild(QWidget, "clayPeek4").parentWidget()
    before = friday.geometry()
    view.findChild(QPushButton, "clayAhead").click()
    qapp.processEvents()
    assert view.row._slide.state() == QAbstractAnimation.State.Running
    assert view.row._slide.duration() == motion.duration(240, "normal")
    assert front(view).tracks[0].day == 4
    landed(qapp, view)
    thursday = view.row.findChild(QWidget, "clayPeek3").parentWidget()
    assert thursday.isVisible() and thursday.geometry().right() < before.left()
    motion.apply_ui_effects("off")
    view.findChild(QPushButton, "clayAhead").click()
    assert view.row._slide.state() == QAbstractAnimation.State.Stopped
    assert view.row.front == 5


def test_under_reduce_the_row_changes_where_it_is_under_a_fading_picture(qapp: QApplication) -> None:
    """Clay's own motion keeps to the levels. Reduce fades and moves nothing; More slides longer than
    Normal."""
    view = shown(qapp)
    motion.apply_ui_effects("reduce")
    view.findChild(QPushButton, "clayAhead").click()
    assert view.row._slide.state() == QAbstractAnimation.State.Stopped, "nothing slides"
    assert view.row.front == 4 and front(view).tracks[0].day == 4, "Friday is in front at once"

    def fading() -> list[QLabel]:
        return [label for label in view.row.findChildren(QLabel, motion.FADE_NAME) if label.isVisible()]

    assert len(fading()) == 1, "the row as it was fades away over it"
    wait_until(qapp, lambda: fading() == [], what="the fade finishing")
    motion.apply_ui_effects("extra")
    view.findChild(QPushButton, "clayAhead").click()
    assert view.row._slide.duration() == motion.duration(240, "extra") > 240


def test_the_row_is_seven_eighths_of_the_way_at_half_time(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    view = shown(qapp)
    motion.apply_ui_effects("normal")
    view.findChild(QPushButton, "clayAhead").click()
    shares = []
    monkeypatch.setattr(view.row, "_slid", shares.append)
    view.row._slide.pause()
    view.row._slide.setCurrentTime(120)
    assert shares == [pytest.approx(0.875)]
    view.row._slide.stop()


def test_the_live_hours_stay_where_they_land_while_the_row_slides(qapp: QApplication) -> None:
    """The hours in front are not painted while the pictures move, so they must not be moved
    either: a widget moved with its updates off leaves stale pixels behind."""
    view = shown(qapp)
    motion.apply_ui_effects("normal")
    row = view.row
    view.findChild(QPushButton, "clayAhead").click()
    assert row._slide.state() == QAbstractAnimation.State.Running
    row._slide.pause()
    row._on_clock(row._slide.duration() / 2)
    assert row._snaps is not None
    mid = row.hours.geometry()
    row._land()
    assert mid == row.hours.geometry()
    row._slide.stop()


def test_a_card_entering_from_off_screen_has_a_picture(qapp: QApplication) -> None:
    """Saturday in front leaves Monday past the left edge; sliding to Sunday still keeps a picture
    of it, so it does not pop if it comes into view."""
    view = shown(qapp)
    view.row._go(5, "jump")
    monday = view.row._rects[0]
    assert monday.right() < 0, "Monday should start past the left edge"
    motion.apply_ui_effects("normal")
    view.row._go(6, "slide")
    assert view.row._slide.state() == QAbstractAnimation.State.Running
    starts, ends = slide_pictures(view.row)
    assert 0 in starts or 0 in ends, "Monday has no start or end picture"
    stop_slide(view.row)


def test_the_end_picture_takes_over_from_the_start_picture_between_15_and_55_percent(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    takeover_between_the_pictures(slide_week(qapp), monkeypatch)
