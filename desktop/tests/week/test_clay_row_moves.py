"""Clay deck's row on Week: the arrows, the wheel and the drag slide it a day at a time, a held block
resting on an arrow does too, and a click on a neighbour still opens its day or its block."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QAbstractAnimation, QCursor, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from desktop.native import motion  # noqa: E402
from desktop.native.hours.canvas import HoursCanvas  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.week.support_clay import (  # noqa: E402, F401
    at_slots,
    card_of,
    drag,
    front,
    landed,
    let_go_at,
    shown,
    still,
    visible_scrolls,
    wheel,
)


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-clay-test"])
    yield application


def test_the_arrows_slide_the_row_a_day_and_stop_at_the_weeks_ends(qapp: QApplication) -> None:
    view = shown(qapp)
    opened: list[str] = []
    view.day_activated.connect(opened.append)
    ahead = view.findChild(QPushButton, "clayAhead")
    back = view.findChild(QPushButton, "clayBack")
    ahead.click()
    assert view.row.front == 4
    assert [track.day for track in front(view).tracks] == [4]
    assert view.findChild(QPushButton, "clayWeekFront").day == 4
    for _ in range(4):
        back.click()
    assert view.row.front == 0
    assert not back.isEnabled() and ahead.isEnabled()
    for _ in range(6):
        ahead.click()
    assert view.row.front == 6
    assert back.isEnabled() and not ahead.isEnabled()
    assert opened == []


def test_the_wheel_slides_the_row_over_a_neighbour_and_scrolls_the_hours_over_the_front(
    qapp: QApplication,
) -> None:
    view = shown(qapp)
    friday = view.findChild(HoursCanvas, "clayPeek4")
    wheel(friday, -1)
    assert view.row.front == 4
    # At the top of the hours, where the wheel has nothing left to scroll and passes on to the row.
    visible_scrolls(view)[0].verticalScrollBar().setValue(0)
    wheel(front(view), 1)
    assert view.row.front == 4


def test_a_block_held_on_an_arrow_slides_the_row_to_the_next_day(qapp: QApplication) -> None:
    """How a block reaches a day that is not beside the one in front: rest it on an arrow."""
    view = shown(qapp)
    ahead = view.findChild(QPushButton, "clayAhead")
    QCursor.setPos(ahead.mapToGlobal(ahead.rect().center()))
    view.hand.active_changed.emit(True)
    # The row waits half a second of the pointer's own time on the arrow before it slides.
    wait_until(qapp, lambda: view.row.front == 4, what="the row sliding after a rest on the arrow")
    view.hand.active_changed.emit(False)
    assert not view.row._dwell.isActive(), "let go, the rest on the arrow slides nothing more"
    assert view.row.front == 4


def test_a_sideways_drag_on_a_neighbour_slides_the_row_to_that_day(qapp: QApplication) -> None:
    """Only the arrows and the wheel used to switch days. Dragged left from Friday, the row brings
    Friday to the front as the ahead arrow does, and nothing is picked up or made."""
    view = shown(qapp)
    made: list[object] = []
    view.hand.committed.connect(made.append)
    friday = view.findChild(HoursCanvas, "clayPeek4")
    drag(friday, friday.rect().center(), QPoint(-200, 0))
    assert view.row.front == 4
    assert [track.day for track in front(view).tracks] == [4]
    assert at_slots(view, 4)
    assert made == [] and not view.hand.busy


def test_a_sideways_drag_on_the_room_between_the_cards_slides_the_row(qapp: QApplication) -> None:
    view = shown(qapp)
    ahead = view.findChild(QPushButton, "clayAhead").geometry()
    gap = QPoint(ahead.center().x(), ahead.top() - 60)
    assert not view.row._rects[3].contains(QPointF(gap)) and not card_of(view, 4).geometry().contains(gap)
    drag(view.row, gap, QPoint(200, 0))
    assert view.row.front == 2
    assert at_slots(view, 2)


def test_a_drag_on_the_front_cards_hours_is_the_hands_and_never_moves_the_row(qapp: QApplication) -> None:
    view = shown(qapp)
    scroll = visible_scrolls(view)[0]
    hours = front(view)
    start = hours.mapFrom(scroll.viewport(), scroll.viewport().rect().center())
    before = (scroll.geometry(), card_of(view, 4).geometry())
    drag(hours, start, QPoint(-150, 0), let_go=False)
    try:
        assert view.hand.active, "the hand carries what the press picked up"
        assert (scroll.geometry(), card_of(view, 4).geometry()) == before
    finally:
        let_go_at(hours, hours.mapTo(view, start + QPoint(-150, 0)))
    assert view.row.front == 3
    assert at_slots(view, 3)


def test_a_drag_shorter_than_40_pixels_goes_back_to_the_day_it_left(qapp: QApplication) -> None:
    view = shown(qapp)
    friday = view.findChild(HoursCanvas, "clayPeek4")
    before = card_of(view, 4).geometry()
    start = friday.mapTo(view, friday.rect().center())
    drag(friday, friday.rect().center(), QPoint(-36, 0), let_go=False)
    try:
        assert card_of(view, 4).geometry() == before.translated(-36, 0), "the row follows the pointer"
    finally:
        let_go_at(friday, start + QPoint(-36, 0))
    assert view.row.front == 3
    assert card_of(view, 4).geometry() == before
    drag(friday, friday.rect().center(), QPoint(-44, 0))
    assert view.row.front == 4


def test_a_drag_settles_with_the_apps_motion_and_at_once_with_motion_off(qapp: QApplication) -> None:
    view = shown(qapp)
    friday = view.findChild(HoursCanvas, "clayPeek4")
    drag(friday, friday.rect().center(), QPoint(-200, 0))
    assert view.row._slide.state() == QAbstractAnimation.State.Stopped
    assert view.row.front == 4 and at_slots(view, 4)
    motion.apply_ui_effects("normal")
    saturday = view.findChild(HoursCanvas, "clayPeek5")
    drag(saturday, saturday.rect().center(), QPoint(-200, 0))
    assert view.row.front == 5
    assert view.row._slide.state() == QAbstractAnimation.State.Running
    landed(qapp, view)
    assert at_slots(view, 5)
    friday = view.findChild(HoursCanvas, "clayPeek4")
    drag(friday, friday.rect().center(), QPoint(20, 0))
    assert view.row.front == 5
    assert view.row._slide.state() == QAbstractAnimation.State.Running, "a short drag slides back"
    landed(qapp, view)
    assert at_slots(view, 5)


def test_a_click_on_a_neighbour_still_opens_its_day_or_its_block(qapp: QApplication) -> None:
    """The row holds a press on a neighbour back until it knows it is no drag of the row; a click is
    then the click it was."""
    view = shown(qapp)
    days: list[str] = []
    blocks: list[str] = []
    view.day_activated.connect(days.append)
    view.hand.opened.connect(blocks.append)
    QTest.mouseClick(view.findChild(QPushButton, "clayDay4"), Qt.MouseButton.LeftButton)
    assert days == [view.scene.week.date_of(4).isoformat()]
    friday = view.findChild(HoursCanvas, "clayPeek4")
    school = friday.block_rect("school", 4)
    assert school is not None
    on_school = friday.mapFromGlobal(school.center())
    QTest.mouseClick(friday, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, on_school)
    assert blocks == ["school"]
    assert view.row.front == 3
