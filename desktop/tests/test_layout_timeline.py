"""Timeline, one day as a column: what it says, and that its options change the column."""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator

import pytest

from desktop.tests.test_weekmodel import BLOCKS, HOMEWORK, TRACE, WEEK

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton

    from desktop.native.layouts.base import Scene
    from desktop.native.layouts.registry import options_for, tokens_for
    from desktop.native.layouts.timeline import TimelineView
    from desktop.native.look import resolved_palette
    from desktop.native.weekmodel import build_week, minute_of


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-timeline-test"])
    yield application


def shown(qapp: QApplication, clock: str = "13:40", today: int | None = 3, **chosen: str) -> TimelineView:
    options = {**options_for(None, "timeline"), **chosen}
    palette = resolved_palette("light-frost", False, None, "default")
    view = TimelineView()
    view.resize(1366, 900)
    week = build_week(WEEK, BLOCKS, HOMEWORK, TRACE)
    view.show_week(
        Scene(week, today, minute_of(clock), options, tokens_for("timeline", options["colour"], palette))
    )
    view.show()
    qapp.processEvents()
    return view


def cards(view: TimelineView) -> list[tuple[str, str]]:
    found = [item for item in view.findChildren(QPushButton) if item.objectName().startswith("timelineRow")]
    return [(item.text().splitlines()[-2].split("   ")[1], item.property("state")) for item in found]


def test_the_heading_says_the_day_and_what_is_left_to_place(qapp: QApplication) -> None:
    view = shown(qapp)
    assert view.findChild(QLabel, "timelineDay").text() == "Thursday"
    assert (
        view.findChild(QLabel, "timelineSub").text()
        == "September 17 · 2 h 30 min planned · 0 done"
    )


def test_the_column_marks_what_is_over_and_what_is_next(qapp: QApplication) -> None:
    assert cards(shown(qapp)) == [("School", ""), ("Dinner", "next"), ("Essay-1", ""), ("Chem-1", "")]
    assert cards(shown(qapp, "19:00")) == [
        ("School", "past"),
        ("Dinner", "past"),
        ("Essay-1", ""),
        ("Chem-1", "next"),
    ]
    assert shown(qapp, "19:00").findChild(QLabel, "timelineNow").text() == "NOW 19:00"


def test_the_next_card_says_how_soon_and_is_tall_enough_for_its_three_lines(qapp: QApplication) -> None:
    view = shown(qapp)
    # A short window squeezes every row to its minimum, which is where the card lost two of its lines.
    view.resize(1366, 380)
    qapp.processEvents()
    card = next(item for item in view.findChildren(QPushButton) if item.property("state") == "next")
    assert card.text().splitlines() == ["UP NEXT · IN 4 H 20 MIN", "18:00   Dinner", "30 min · Meals"]
    assert card.height() >= 3 * card.fontMetrics().lineSpacing() + 12


def test_homework_cards_carry_the_deadline_and_the_solvers_verdict(qapp: QApplication) -> None:
    view = shown(qapp)
    chem = next(item for item in view.findChildren(QPushButton) if item.property("block_id") == "chem-1")
    assert chem.text().splitlines()[-1] == "1 h 30 min · Homework · due Thu 17 Sep · Cutting it close"


def test_the_inbox_lists_what_has_no_time_and_offers_to_plan_it(qapp: QApplication) -> None:
    view = shown(qapp)
    assert view.findChild(QPushButton, "timelineWaiting0").text() == (
        "Poster-1\n2 h · due Sun 20 Sep, 20:00 · There is not enough time left before it is due,"
        " even with nothing else planned."
    )
    asked: list[str] = []
    view.plan_requested.connect(lambda: asked.append("plan"))
    view.findChild(QPushButton, "timelineInboxPlan").click()
    assert asked == ["plan"]


def test_the_strip_opens_another_day(qapp: QApplication) -> None:
    view = shown(qapp)
    view.findChild(QPushButton, "timelineDay0").click()
    assert view.findChild(QLabel, "timelineDay").text() == "Monday"
    assert cards(view) == [("School", "past"), ("Math-1", "past"), ("Dinner", "past")]
    assert view.findChild(QLabel, "timelineNow") is None


def test_the_next_homework_offers_focus(qapp: QApplication) -> None:
    view = shown(qapp, "18:35")
    asked: list[tuple] = []
    view.focus_requested.connect(lambda block, day: asked.append((block, day)))
    view.findChild(QPushButton, "timelineFocus").click()
    assert asked == [("essay-1", 3)]


def test_option_finished_hidden_drops_what_is_over(qapp: QApplication) -> None:
    assert cards(shown(qapp, "19:00", finished="hide")) == [("Essay-1", ""), ("Chem-1", "next")]


def test_option_strip_with_and_without_load_bars(qapp: QApplication) -> None:
    def bars(view: TimelineView) -> int:
        return len([item for item in view.findChildren(QFrame) if item.property("role") == "load"])

    assert (bars(shown(qapp)), bars(shown(qapp, strip="names"))) == (7, 0)
    assert shown(qapp, strip="names").findChild(QPushButton, "timelineDay6") is not None


def test_option_compact_tightens_the_column(qapp: QApplication) -> None:
    def height(view: TimelineView) -> int:
        return view.findChild(QPushButton, "timelineRow0").height()

    assert height(shown(qapp, density="compact")) < height(shown(qapp))


def test_option_colours_repaint_the_page(qapp: QApplication) -> None:
    def corner(view: TimelineView) -> str:
        return view.grab().toImage().pixelColor(5, 5).name()

    assert (corner(shown(qapp)), corner(shown(qapp, colour="night"))) == ("#f6f4ef", "#14161c")


def test_a_load_bar_sits_in_a_track_of_its_own(qapp: QApplication) -> None:
    """Bare stubs of different widths under each day read as debris, not as a chart."""
    view = shown(qapp)
    tracks = [item for item in view.findChildren(QFrame) if item.property("role") == "track"]
    bars = [item for item in view.findChildren(QFrame) if item.property("role") == "load"]
    assert len(tracks) == 7 and len(bars) == 7
    widths = sorted(track.width() for track in tracks)
    assert widths[-1] - widths[0] <= 2, f"tracks should share a width, got {widths}"
    assert all(bar.width() <= track.width() for bar, track in zip(bars, tracks, strict=True))
    busiest = max(range(7), key=lambda day: view.scene.week.load_min(day))
    assert bars[busiest].width() == max(bar.width() for bar in bars)
