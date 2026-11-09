"""Mission control's week: seven lanes of hours on the shared hand, a day's name that opens the day, a bar
that opens and names itself, and the lanes' zoom. (How the lanes look is the pictures week.mission_*.)"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import replace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QHelpEvent, QMouseEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QFrame, QPushButton, QToolTip, QWidget  # noqa: E402

from desktop.native.hours.chips import TrayChip  # noqa: E402
from desktop.native.hours.geometry import Axis, Span  # noqa: E402
from desktop.native.hours.hand import Hand, Move, Verdict  # noqa: E402
from desktop.native.layouts.mission import MissionCanvas  # noqa: E402
from desktop.native.layouts.registry import DESIGN_LOOKS  # noqa: E402
from desktop.tests.day.support_mission import BLOCKS, block, shown  # noqa: E402

CLUB = block("club", "locked", [0], "15:15", 45, title="Robotics club", category="extra")


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-mission-week-test"])


def test_week_has_seven_live_horizontal_tracks_and_one_hand(qapp: QApplication) -> None:
    view = shown(qapp)
    hours = view.findChild(MissionCanvas, "missionHours")
    assert view.hours_surfaces() == [hours]
    assert [track.day for track in hours.tracks] == list(range(7))
    assert all(track.axis is Axis.ACROSS and track.first == 0 and track.last == 1440
               for track in hours.tracks)
    assert hours.hand is view.hand
    chip = view.findChild(TrayChip, "missionWaiting0")
    assert (chip.block_id, chip.text()) == ("poster-1", "Not placed yet")


def test_a_block_sharing_its_time_is_picked_up_and_dropped_on_another_lane(qapp: QApplication) -> None:
    host = QWidget()
    hand = Hand(lambda block_id, from_day, span: Verdict(True, ""), host)
    said: list[object] = []
    hand.committed.connect(said.append)
    view = shown(qapp, blocks=[*BLOCKS, CLUB], size=(1280, 744), hand=hand)
    hours = view.findChild(MissionCanvas, "missionHours")
    start = hours.block_rect("math-1", 0).center()
    # 70 pixels at 56 an hour is an hour and a quarter later, in Tuesday's lane.
    end = QPoint(start.x() + 70, hours.point_for(1, 12 * 60).y())

    def send(kind: QEvent.Type, at: QPoint, held: bool) -> None:
        buttons = Qt.MouseButton.LeftButton if held else Qt.MouseButton.NoButton
        event = QMouseEvent(kind, QPointF(hours.mapFromGlobal(at)), QPointF(at), Qt.MouseButton.LeftButton,
                            buttons, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(hours, event)

    send(QEvent.Type.MouseButtonPress, start, True)
    for step in range(1, 9):
        send(QEvent.Type.MouseMove, start + (end - start) * step / 8, True)
    send(QEvent.Type.MouseButtonRelease, end, False)
    assert said == [Move("math-1", 0, Span(1, 17 * 60, 17 * 60 + 45))]


def test_week_name_opens_a_real_day_and_todays_date_is_a_chip(qapp: QApplication) -> None:
    view = shown(qapp)
    opened: list[str] = []
    view.day_activated.connect(opened.append)
    view.findChild(QPushButton, "missionDay4").click()
    assert opened == [view.scene.week.date_of(4).isoformat()]
    today, friday = view.findChild(QPushButton, "missionDay3"), view.findChild(QPushButton, "missionDay4")
    assert (today.chip.isVisible(), today.date.isVisible(), today.chip.text()) == (True, False, "17")
    assert (friday.chip.isVisible(), friday.date.isVisible(), friday.date.text()) == (False, True, "18")


def test_a_bar_opens_and_gives_its_name_and_times_on_hover(qapp: QApplication) -> None:
    """How a tick too small for its name is named, and a bar's name that did not fit whole."""
    view = shown(qapp)
    hours = view.findChild(MissionCanvas, "missionHours")
    box = hours.block_rect("chem-1", 3)
    local = hours.mapFromGlobal(box.center())
    opened: list[str] = []
    hours.hand.opened.connect(opened.append)
    QTest.mouseDClick(hours, Qt.MouseButton.LeftButton, pos=local)
    QTest.mouseRelease(hours, Qt.MouseButton.LeftButton, pos=local)
    assert opened == ["chem-1"]
    QApplication.sendEvent(hours, QHelpEvent(QEvent.Type.ToolTip, local, box.center()))
    # N11: "Placed by Plan" lives in the tooltip, never on the bar (it must not push out the time).
    assert QToolTip.text() == "Chem-1\n20:00–21:30 · 1 h 30 min · Placed by Plan"


def test_the_lanes_cover_the_whole_day_so_an_early_block_and_a_quarter_hour_have_a_bar(
    qapp: QApplication,
) -> None:
    blocks = [*BLOCKS, block("paper-round", "locked", [3], "05:00", 45),
              block("quiz", "locked", [4], "10:00", 15)]
    view = shown(qapp, blocks=blocks)
    hours = view.findChild(MissionCanvas, "missionHours")
    assert hours.block_rect("paper-round", 3) is not None
    assert hours.block_rect("quiz", 4) is not None


def test_the_figures_can_be_hidden(qapp: QApplication) -> None:
    assert shown(qapp, figures="hide").findChild(QFrame, "missionStrip") is None
    assert shown(qapp).findChild(QFrame, "missionStrip") is not None


def test_a_narrow_week_keeps_its_hours_and_their_zoom(qapp: QApplication) -> None:
    view = shown(qapp)
    original = view._scrolls["week"]
    original.zoom_by(1)
    view.resize(800, 640)
    view.show_week(replace(view.scene, minute=view.scene.minute + 1))
    # The board is laid out in one pass, and its scroll area grows the page to hold it in the next.
    for _ in range(2):
        qapp.processEvents()
    assert view.findChild(TrayChip, "missionWaiting0") is not None
    assert view._scrolls["week"] is original
    assert original.px == 72
    view.show_week(replace(view.scene, surface="day"))
    view.show_week(replace(view.scene, surface="week"))
    assert view._scrolls["week"] is original and original.px == 72


def test_flight_deck_is_the_first_look_mission_offers() -> None:
    assert DESIGN_LOOKS["mission"][0] == ("preset:flight-deck", "Flight deck")
