"""Mission's scope and lanes use the shared hand, with their own HUD and cargo tray."""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator
from dataclasses import replace

import pytest

from desktop.tests.test_weekmodel import BLOCKS, HOMEWORK, TRACE, WEEK, block

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    import shiboken6
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QHelpEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QToolTip, QVBoxLayout, QWidget

    from desktop.native.hours.chips import TrayChip
    from desktop.native.hours.geometry import Axis
    from desktop.native.layouts.base import Scene
    from desktop.native.layouts.mission import MissionCanvas, MissionView
    from desktop.native.layouts.registry import options_for, tokens_for
    from desktop.native.look import resolved_palette
    from desktop.native.weekmodel import build_week, minute_of


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-mission-test"])


def shown(qapp: QApplication, *, surface: str = "week", blocks: list[dict] | None = None,
          iso_day: str = "", **chosen: str) -> MissionView:
    options = {**options_for(None, "mission"), **chosen}
    palette = resolved_palette("light-frost", False, None, "default")
    view = MissionView()
    view.resize(1366, 760)
    week = build_week(WEEK, blocks or BLOCKS, HOMEWORK, TRACE)
    view.show_week(Scene(week, 3, minute_of("13:40"), options,
                         tokens_for("mission", options["colour"], palette),
                         surface=surface, iso_day=iso_day))
    view.show()
    qapp.processEvents()
    return view


def test_week_has_seven_live_horizontal_tracks_and_one_hand(qapp: QApplication) -> None:
    view = shown(qapp)
    hours = view.findChild(MissionCanvas, "missionHours")
    assert view.hours_surfaces() == [hours]
    assert [track.day for track in hours.tracks] == list(range(7))
    assert all(track.axis is Axis.ACROSS and track.first == 0 and track.last == 1440
               for track in hours.tracks)
    assert hours.hand is view.hand
    assert view.uses_drawer is False
    assert view.findChild(TrayChip, "missionWaiting0") is not None
    assert view.findChild(QLabel, "missionUnplaced").text().startswith("NOT PLACED YET")


def test_day_scope_uses_the_selected_date_and_has_cargo_bay(qapp: QApplication) -> None:
    view = shown(qapp, surface="day", iso_day="2026-09-18")
    hours = view.findChild(MissionCanvas, "missionHours")
    assert len(hours.tracks) == 1
    assert hours.tracks[0].day == 4
    assert hours.tracks[0].axis is Axis.ACROSS
    assert view.findChild(QFrame, "missionCargo") is not None
    assert view.findChild(QFrame, "missionSide") is None
    assert view.findChild(QLabel, "missionTitle").text().startswith("FLEXWEEK / DAY")


def test_two_blocks_at_one_time_take_separate_scope_rows(qapp: QApplication) -> None:
    view = shown(qapp, surface="day", blocks=[*BLOCKS, block("quiz", "locked", [3], "18:00", 60)])
    hours = view.findChild(MissionCanvas, "missionHours")
    track = hours.track_for(3)
    boxes = [rect for item, rect in hours.drawn(track) if item.block_id in {"dinner", "quiz"}]
    assert len(boxes) == 2
    assert boxes[0].bottom() < boxes[1].top() or boxes[1].bottom() < boxes[0].top()


def test_week_name_opens_a_real_day(qapp: QApplication) -> None:
    view = shown(qapp)
    opened: list[str] = []
    view.day_activated.connect(opened.append)
    view.findChild(QPushButton, "missionDay4").click()
    assert opened == [view.scene.week.date_of(4).isoformat()]


def test_a_bar_opens_and_gives_its_full_name_on_hover(qapp: QApplication) -> None:
    view = shown(qapp)
    hours = view.findChild(MissionCanvas, "missionHours")
    box = hours.block_rect("chem-1", 3)
    local = hours.mapFromGlobal(box.center())
    opened: list[str] = []
    hours.hand.opened.connect(opened.append)
    QTest.mouseDClick(hours, Qt.MouseButton.LeftButton, pos=local)
    assert opened == ["chem-1"]
    QApplication.sendEvent(hours, QHelpEvent(QEvent.Type.ToolTip, local, box.center()))
    assert QToolTip.text() == "Chem-1"


def test_header_and_radar_keep_missions_status(qapp: QApplication) -> None:
    view = shown(qapp)
    said = [view.findChild(QLabel, name).text() for name in
            ("missionTitle", "missionClock", "missionPlaced")]
    assert said == ["FLEXWEEK / WEEK 38", "LOCAL 13:40", "PLAN 3/4 PLACED"]
    assert view.findChild(QPushButton, "missionRadar0").property("risk") == "danger"
    assert view.findChild(QLabel, "missionLoadTitle") is not None


def test_full_day_reaches_early_block_and_quarter_hour(qapp: QApplication) -> None:
    blocks = [*BLOCKS, block("paper-round", "locked", [3], "05:00", 45),
              block("quiz", "locked", [4], "10:00", 15)]
    view = shown(qapp, blocks=blocks)
    hours = view.findChild(MissionCanvas, "missionHours")
    assert hours.block_rect("paper-round", 3) is not None
    assert hours.block_rect("quiz", 4).width() >= 14
    assert hours.block_rect("quiz", 4).height() >= 14


def test_side_can_hide_without_hiding_the_tray(qapp: QApplication) -> None:
    view = shown(qapp, side="hide")
    assert view.findChild(QFrame, "missionSide") is None
    assert view.findChild(TrayChip, "missionWaiting0") is not None


def test_narrow_week_keeps_the_tray_and_its_zoom(qapp: QApplication) -> None:
    view = shown(qapp)
    original = view._scrolls["week"]
    original.zoom_by(1)
    view.resize(1024, 640)
    view.show_week(replace(view.scene, minute=view.scene.minute + 1))
    qapp.processEvents()
    assert view.findChild(QFrame, "missionSide") is None
    assert view.findChild(TrayChip, "missionWaiting0") is not None
    assert view._scrolls["week"] is original
    assert original.px == 96
    view.show_week(replace(view.scene, surface="day"))
    view.show_week(replace(view.scene, surface="week"))
    assert view._scrolls["week"] is original and original.px == 96


def test_parked_day_scroll_dies_with_its_host(qapp: QApplication) -> None:
    options = options_for(None, "mission")
    palette = resolved_palette("light-frost", False, None, "default")
    week = build_week(WEEK, BLOCKS, HOMEWORK, TRACE)
    scene = Scene(week, 3, minute_of("13:40"), options,
                  tokens_for("mission", options["colour"], palette))
    host = QWidget()
    view = MissionView(host)
    QVBoxLayout(host).addWidget(view)
    view.show_week(scene)
    host.show()
    qapp.processEvents()
    view.show_week(replace(scene, surface="day", iso_day="2026-09-18"))
    parked = view._scrolls["day"]
    view.show_week(scene)
    assert shiboken6.isValid(parked)

    host.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not shiboken6.isValid(parked)


def test_colour_option_repaints_the_console(qapp: QApplication) -> None:
    colours = [shown(qapp, colour=name).grab().toImage().pixelColor(3, 3).name()
               for name in ("cyan", "amber", "green")]
    assert colours == ["#070b12", "#0d0a04", "#040b06"]


def test_radar_elides_a_long_title(qapp: QApplication) -> None:
    title = "History essay outline and annotated bibliography"
    blocks = [{**item, "title": title} if item["id"] == "essay-1" else item for item in BLOCKS]
    view = shown(qapp, blocks=blocks)
    row = view.findChild(QPushButton, "missionRadar1")
    assert "…" in row.text()
    assert row.toolTip() == title


def test_cargo_chip_click_opens_homework(qapp: QApplication) -> None:
    view = shown(qapp, surface="day")
    opened: list[str] = []
    view.block_activated.connect(opened.append)
    chip = view.findChild(TrayChip, "missionWaiting0")
    QTest.mouseClick(chip, Qt.MouseButton.LeftButton)
    assert opened == [chip.block_id]
