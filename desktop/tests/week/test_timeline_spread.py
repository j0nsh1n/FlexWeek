"""Timeline, the planner spread on Week: seven columns on two pages of one canvas with the day names over
them, what a block says, the week's figures, the notes and what is due at the foot of the pages."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QBoxLayout, QLabel, QPushButton, QWidget  # noqa: E402

from desktop.native.hours.chips import TrayChip  # noqa: E402
from desktop.native.hours.geometry import Axis  # noqa: E402
from desktop.native.layouts.timeline import (  # noqa: E402
    Due,
    Split,
    _due_words,
    due_this_week,
    week_figures,
)
from desktop.native.weekmodel import build_week  # noqa: E402
from desktop.native.widgets import FittedLabel, use_app_style  # noqa: E402
from desktop.tests.test_weekmodel import BLOCKS, HOMEWORK, TRACE, WEEK, block  # noqa: E402
from desktop.tests.week.support_timeline import (  # noqa: E402
    canvas,
    drawn_words,
    plain,
    scroll_of,
    shown,
    texts,
)


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-timeline-test"])
    use_app_style(application)
    yield application


def test_week_paints_the_history_essay_title_on_a_sixty_minute_block(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    blocks = [
        {**item, "title": "History essay"} if item["id"] == "essay-1" else item for item in BLOCKS
    ]
    said = drawn_words(monkeypatch, shown(qapp, size=(1280, 800), blocks=blocks))
    assert "History essay" in said


def test_week_is_seven_columns_on_two_pages_of_one_canvas(qapp: QApplication) -> None:
    view = shown(qapp)
    hours = canvas(view)
    assert [(track.day, track.axis, track.first, track.last) for track in hours.tracks] == [
        (day, Axis.DOWN, 0, 1440) for day in range(7)
    ]
    assert hours.hand is view.hand and scroll_of(view).axis is Axis.DOWN


def test_each_days_name_sits_over_its_column_and_opens_it(qapp: QApplication) -> None:
    view = shown(qapp)
    hours = canvas(view)
    for track in hours.tracks:
        heading = view.findChild(QPushButton, f"timelineWeekDay{track.day}")
        assert hours.day_name(track.day) == heading.mapToGlobal(heading.rect().center())
    names = [view.findChild(QPushButton, f"timelineWeekDay{day}").title.text() for day in range(7)]
    assert names == ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    assert texts(view, "timelineChip") == ["17"], "today's date is the one chip"
    assert texts(view, "timelineDate") == ["14", "15", "16", "18", "19", "20"]
    opened: list[str] = []
    view.day_activated.connect(opened.append)
    QTest.mouseClick(view.findChild(QPushButton, "timelineWeekDay4"), Qt.MouseButton.LeftButton)
    assert opened == ["2026-09-18"]


@pytest.mark.parametrize("size", [(1280, 744), (800, 700)])
def test_a_days_name_shortens_before_it_is_cut(qapp: QApplication, size: tuple[int, int]) -> None:
    view = shown(qapp, size=size)
    for day, short in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")):
        title = view.findChild(QPushButton, f"timelineWeekDay{day}").title
        assert "…" not in title.text() and title.text().startswith(short), title.text()


def test_the_weeks_blocks_say_their_times_and_not_their_length(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    week = drawn_words(monkeypatch, shown(qapp))
    assert "08:00–14:30" in week and not any("6 h 30 min" in words for words in week)


def test_now_is_written_with_its_time_on_todays_column(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert "15:40" in drawn_words(monkeypatch, shown(qapp, clock="15:40"))


def test_the_left_pages_foot_gives_the_week_in_figures_and_what_is_next(qapp: QApplication) -> None:
    view = shown(qapp)
    assert "This week" in texts(view, "timelineLabel")
    assert list(zip(texts(view, "timelineStat"), texts(view, "timelineStatWord"), strict=True)) == [
        ("3 h 15 min", "homework planned"),
        ("1 of 4", "done"),
        ("1", "not placed yet"),
    ]
    (line,) = view.findChildren(QLabel, "timelineNext")
    assert plain(line) == "Next Dinner at 18:00, in 4 h 20 min"


def test_the_right_pages_foot_holds_the_notes_and_what_is_due_this_week(qapp: QApplication) -> None:
    view = shown(qapp)
    assert texts(view, "timelineTrayLabel") == ["Not placed yet"]
    notes = [chip for chip in view.findChildren(TrayChip) if chip.isVisible()]
    assert [(chip.held.title, chip.hand is view.hand, chip.text()) for chip in notes] == [
        ("Poster-1", True, "Poster-1")
    ]
    opened: list[str] = []
    view.block_activated.connect(opened.append)
    QTest.mouseClick(notes[0], Qt.MouseButton.LeftButton)
    assert opened == ["poster-1"]
    rows = [
        (row.findChild(FittedLabel, "timelineDueTitle").full_text(), row.findChild(QLabel, "timelineDueWhen"))
        for row in view.findChildren(QWidget, "timelineDueRow")
        if row.isVisible()
    ]
    assert notes[0].due == "due Sun 20 Sep"
    assert [(title, when.text()) for title, when in rows] == [
        ("Poster-1", "due Sun 20 Sep · Not placed yet"),
        ("Math-1", "due Tue 15 Sep · placed Mon 15:45"),
        ("Essay-1", "due Fri 18 Sep · placed Thu 18:45"),
        ("Chem-1", "due Thu 17 Sep · placed Thu 20:00"),
    ]
    assert [bool(when.property("open")) for _title, when in rows] == [True, False, False, False]


def test_a_deadline_reads_due_weekday_day_and_month() -> None:
    """A due date is the weekday, the day number and the month, never the day number alone."""
    assert _due_words("2026-10-04") == "due Sun 4 Oct"
    assert _due_words("2026-10-04T15:30") == "due Sun 4 Oct"
    assert _due_words(None) == ""


def test_what_waits_is_listed_first_and_what_is_due_later_is_left_out() -> None:
    blocks = [
        *BLOCKS,
        # Two sessions of the essay, one of them still waiting: the essay is not placed yet.
        block("essay-2", "flexible", [], None, 30, assignment_id="essay", title="Essay-2"),
        block("lab-1", "flexible", [4], "16:00", 60, assignment_id="lab", title="Lab write-up"),
    ]
    homework = {
        **HOMEWORK,
        "lab": {"id": "lab", "title": "Lab", "due": "2026-09-22T23:59", "completed": False},
    }
    listed = due_this_week(build_week(WEEK, blocks, homework, TRACE))
    assert listed == [
        Due("Essay-2", None, "2026-09-18T21:00"),
        Due("Poster-1", None, "2026-09-20T20:00"),
        Due("Math-1", (0, 15 * 60 + 45), "2026-09-15T08:00"),
        Due("Chem-1", (3, 20 * 60), "2026-09-17T23:59"),
    ]


def test_the_weeks_figures_count_homework_whole_not_its_sessions() -> None:
    blocks = [
        *BLOCKS,
        # A second session of the finished math worksheet, not itself finished.
        block("math-2", "flexible", [2], "16:00", 30, assignment_id="math"),
    ]
    figures = week_figures(
        build_week(WEEK, blocks, {**HOMEWORK, "math": {**HOMEWORK["math"], "completed": False}}, TRACE)
    )
    assert figures == (("3 h 45 min", "homework planned"), ("0 of 4", "done"), ("1", "not placed yet"))
    empty = week_figures(build_week(WEEK, [BLOCKS[0]], {}, None))
    assert empty == (("0 min", "homework planned"), ("0", "done"), ("0", "not placed yet"))


def test_with_nothing_waiting_and_nothing_due_the_foot_says_so(qapp: QApplication) -> None:
    view = shown(qapp, blocks=[BLOCKS[0], BLOCKS[1]], homework={})
    assert texts(view, "timelineHint") == ["Nothing is due this week."]
    assert view.findChildren(TrayChip) == []


@pytest.mark.parametrize(("size", "direction"), [((1280, 744), "side"), ((800, 700), "under")])
def test_the_notes_and_what_is_due_sit_side_by_side_or_one_under_the_other(
    qapp: QApplication, size: tuple[int, int], direction: str
) -> None:
    view = shown(qapp, size=size)
    split = view.findChild(Split, "timelineNotesSplit")
    wanted = QBoxLayout.Direction.LeftToRight if direction == "side" else QBoxLayout.Direction.TopToBottom
    assert split.box.direction() == wanted
    for title in view.findChildren(FittedLabel, "timelineDueTitle"):
        assert title.text() == title.full_text(), title.text()


def test_option_finished_hidden_drops_what_is_over(qapp: QApplication) -> None:
    def drawn(view) -> list[str]:
        return sorted(
            {item.block_id for track in canvas(view).tracks for item, _ in canvas(view).drawn(track)}
        )

    assert drawn(shown(qapp, clock="19:00")) == ["chem-1", "dinner", "essay-1", "math-1", "school"]
    assert drawn(shown(qapp, clock="19:00", finished="hide")) == ["chem-1", "dinner", "essay-1", "school"]
    assert drawn(shown(qapp, "day", clock="19:00", finished="hide")) == ["chem-1", "essay-1"]
