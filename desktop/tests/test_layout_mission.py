"""Mission control: the painted lanes answer a click, the day row is their keyboard twin, and the
options change the screen."""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator

import pytest

from desktop.tests.test_weekmodel import BLOCKS, HOMEWORK, TRACE, WEEK, block

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton

    from desktop.native.layouts.base import Scene
    from desktop.native.layouts.mission import Lanes, MissionView
    from desktop.native.layouts.registry import options_for, tokens_for
    from desktop.native.look import resolved_palette
    from desktop.native.weekmodel import build_week, minute_of


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-mission-test"])
    yield application


def shown(
    qapp: QApplication,
    blocks: list[dict] | None = None,
    homework: dict | None = None,
    today: int | None = 3,
    **chosen: str,
) -> MissionView:
    options = {**options_for(None, "mission"), **chosen}
    palette = resolved_palette("light-frost", False, None, "default")
    view = MissionView()
    view.resize(1366, 760)
    week = build_week(WEEK, blocks or BLOCKS, homework or HOMEWORK, TRACE)
    view.show_week(
        Scene(week, today, minute_of("13:40"), options, tokens_for("mission", options["colour"], palette))
    )
    view.show()
    qapp.processEvents()
    return view


def reachable(lanes: Lanes) -> set[str]:
    hits = set()
    for x in range(0, lanes.width(), 4):
        for y in range(0, lanes.height(), 4):
            found = lanes.block_at(QPointF(x, y))
            if found is not None:
                hits.add(found.block_id)
    return hits


def chips(view: MissionView) -> list[str]:
    return [item.text() for item in view.findChildren(QPushButton) if item.property("kind") == "chip"]


def test_the_header_says_the_week_the_time_and_how_much_is_placed(qapp: QApplication) -> None:
    view = shown(qapp)
    said = [view.findChild(QLabel, name).text() for name in ("missionTitle", "missionClock", "missionPlaced")]
    assert said == ["FLEXWEEK / WEEK 38", "LOCAL 13:40", "PLAN 3/4 PLACED"]


def test_every_block_of_the_week_can_be_clicked_on_the_lanes(qapp: QApplication) -> None:
    assert reachable(shown(qapp).findChild(Lanes)) == {"school", "dinner", "essay-1", "chem-1", "math-1"}


def test_a_click_on_a_bar_opens_it_and_a_click_on_empty_lane_opens_nothing(qapp: QApplication) -> None:
    view = shown(qapp)
    lanes = view.findChild(Lanes)
    opened: list[str] = []
    view.block_activated.connect(opened.append)
    QTest.mouseClick(lanes, Qt.MouseButton.LeftButton, pos=QPoint(lanes.width() - 12, lanes.height() - 12))
    assert opened == []
    spot = lanes.bar_rect(
        next(item for item in view.scene.week.occurrences if item.block_id == "chem-1")
    ).center()
    QTest.mouseClick(lanes, Qt.MouseButton.LeftButton, pos=spot.toPoint())
    assert opened == ["chem-1"]


def test_the_day_row_is_the_keyboard_twin_of_the_lanes(qapp: QApplication) -> None:
    view = shown(qapp)
    assert chips(view) == ["08:00 School", "18:00 Dinner", "18:45 Essay-1", "20:00 Chem-1"]
    view.findChild(QPushButton, "missionDay0").click()
    assert chips(view) == ["08:00 School", "15:45 Math-1", "18:00 Dinner"]
    assert view.findChild(QPushButton, "missionDay0").property("chosen") == "true"


def test_a_click_on_a_lanes_name_picks_that_day(qapp: QApplication) -> None:
    view = shown(qapp)
    lanes = view.findChild(Lanes)
    QTest.mouseClick(lanes, Qt.MouseButton.LeftButton, pos=QPoint(20, lanes.height() - 8))
    assert chips(view) == ["18:00 Dinner"]


def test_the_radar_lists_open_homework_most_squeezed_first_with_the_verdict(qapp: QApplication) -> None:
    view = shown(qapp)
    rows = [view.findChild(QPushButton, f"missionRadar{index}") for index in range(2)]
    assert [(row.text(), row.property("risk")) for row in rows] == [
        ("Chem-1\nThu 23:59 · VERY LITTLE ROOM", "danger"),
        ("Essay-1\nFri 21:00 · LIMITED ROOM", "tight"),
    ]


def test_what_has_no_time_is_named_with_the_solvers_reason(qapp: QApplication) -> None:
    assert shown(qapp).findChild(QPushButton, "missionWaiting0").text() == (
        "Poster-1 · There is no slot left before this deadline."
    )


def test_option_all_24_hours_reaches_the_early_morning(qapp: QApplication) -> None:
    early = [*BLOCKS, block("paper-round", "locked", [3], "05:00", 45)]
    assert "paper-round" not in reachable(shown(qapp, early).findChild(Lanes))
    assert "paper-round" in reachable(shown(qapp, early, hours="full").findChild(Lanes))


def test_option_side_hidden_removes_the_radar_but_not_what_is_unplaced(qapp: QApplication) -> None:
    view = shown(qapp, side="hide")
    assert view.findChild(QFrame, "missionSide") is None
    assert view.findChild(QPushButton, "missionWaiting0") is not None
    assert shown(qapp).findChild(QFrame, "missionSide") is not None


def test_option_colours_repaint_the_console(qapp: QApplication) -> None:
    def corner(view: MissionView) -> str:
        return view.grab().toImage().pixelColor(3, 3).name()

    assert [corner(shown(qapp, colour=name)) for name in ("cyan", "amber", "green")] == [
        "#070b12",
        "#0d0a04",
        "#040b06",
    ]


def test_every_bar_has_visible_text_or_a_tooltip(qapp: QApplication) -> None:
    skinny = [*BLOCKS, block("quiz", "locked", [4], "10:00", 15, title="Quiz")]
    view = shown(qapp, blocks=skinny)
    lanes = view.findChild(Lanes)
    qapp.processEvents()
    seen = []
    for item in view.scene.week.occurrences:
        if not lanes._in_view(item):
            continue
        drawn, hint = lanes.caption(item)
        assert hint == item.title
        assert drawn or hint
        seen.append(item.block_id)
    assert "quiz" in seen
    quiz = next(item for item in view.scene.week.occurrences if item.block_id == "quiz")
    assert lanes.bar_rect(quiz).width() <= 34
    drawn, hint = lanes.caption(quiz)
    assert hint == "Quiz"
    assert drawn == "Q"


def test_the_radar_elides_a_long_title_with_an_ellipsis(qapp: QApplication) -> None:
    long_title = "History essay outline and annotated bibliography"
    blocks = [{**item, "title": long_title} if item["id"] == "essay-1" else item for item in BLOCKS]
    view = shown(qapp, blocks=blocks)
    row = view.findChild(QPushButton, "missionRadar1")
    assert "…" in row.text()
    assert "annotated bibliography" not in row.text().split("\n")[0]
    assert row.toolTip() == long_title


def test_the_radar_steps_aside_on_a_narrow_window(qapp: QApplication) -> None:
    """Mission wanted 1220px. The lanes are the point; the radar repeats what the unplaced strip
    and the day row already say, so it is the first thing to go."""
    wide = shown(qapp)
    wide.resize(1366, 700)
    qapp.processEvents()
    assert wide.findChild(QFrame, "missionSide") is not None

    tight = MissionView()
    tight.resize(1024, 640)
    tight.show()
    qapp.processEvents()
    tight.show_week(wide.scene)
    qapp.processEvents()
    assert tight.cramped is True
    assert tight.findChild(QFrame, "missionSide") is None
    for name in ("missionAdd",):
        button = tight.findChild(QPushButton, name)
        assert button is not None and button.x() + button.width() <= tight.width()
