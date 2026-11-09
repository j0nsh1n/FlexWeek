"""Mission control's deadline table: homework still to do by time left, and the handle for what is not
placed yet."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QFrame, QLabel  # noqa: E402

from desktop.native.hours.chips import TrayChip  # noqa: E402
from desktop.native.layouts.mission import Bar  # noqa: E402
from desktop.native.widgets import FittedLabel  # noqa: E402
from desktop.tests.day.support_mission import BLOCKS, HOMEWORK, block, figure, shown, table_rows  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-mission-deadlines-test"])


def test_the_deadline_table_lists_homework_still_to_do_by_time_left(qapp: QApplication) -> None:
    """Chem is due at the end of today, the essay at 21:00 tomorrow and the poster on Sunday at
    20:00; the finished maths is not listed. The bar is how much of each is placed."""
    view = shown(qapp)
    assert table_rows(view) == [
        ("Chem-1", "1:30", "10 h", "Placed Thu 20:00"),
        ("Essay-1", "1:00", "1 d 7 h", "Placed Thu 18:45"),
        ("Poster-1", "2:00", "3 d 6 h", "Not placed yet"),
    ]
    table = view.findChild(QFrame, "missionDeadlines")
    assert [bar.share for bar in table.findChildren(Bar)] == [1.0, 1.0, 0.0]
    foot = table.findChild(QLabel, "missionFoot").text()
    assert foot == "The bar is how much of each is placed in the week."


def test_homework_due_on_one_day_says_so_under_the_table(qapp: QApplication) -> None:
    homework = {key: {**item, "due": "2026-09-20T23:59"} for key, item in HOMEWORK.items()}
    view = shown(qapp, homework=homework)
    foot = view.findChild(QFrame, "missionDeadlines").findChild(QLabel, "missionFoot").text()
    assert foot == "All 3 are due Sunday 20 September. The bar is how much of each is placed in the week."


def test_part_placed_homework_offers_the_session_still_waiting(qapp: QApplication) -> None:
    """The essay has an hour placed and 45 minutes waiting: its bar is part full, its waiting session
    is the handle to drag, and it counts as not placed yet."""
    second = block("second-wait", "flexible", [], None, 45, assignment_id="essay", title="Second wait")
    blocks = [*BLOCKS, second]
    view = shown(qapp, blocks=blocks)
    essay = table_rows(view)[1]
    assert essay == ("Essay-1", "1:45", "1 d 7 h", "45 min not placed yet")
    share = view.findChild(QFrame, "missionDeadlines").findChildren(Bar)[1].share
    assert share == pytest.approx(60 / 105)
    chips = {chip.block_id for chip in view.findChildren(TrayChip)}
    assert chips == {"poster-1", "second-wait"}
    assert figure(view, "missionDue")[1] == "1 placed, 2 not placed yet"


def test_homework_past_due_says_so(qapp: QApplication) -> None:
    homework = {**HOMEWORK, "essay": {**HOMEWORK["essay"], "due": "2026-09-17T10:00"}}
    view = shown(qapp, homework=homework)
    first = view.findChild(QFrame, "missionDeadlines").findChildren(QLabel, "missionLeft")[0]
    assert (first.text(), first.property("gone")) == ("Past due", True)
    assert table_rows(view)[0][0] == "Essay-1"


def test_a_long_title_in_the_table_is_shortened_with_its_whole_name_to_hand(qapp: QApplication) -> None:
    title = "History essay outline and annotated bibliography"
    blocks = [{**item, "title": title} if item["id"] == "essay-1" else item for item in BLOCKS]
    view = shown(qapp, blocks=blocks)
    name = view.findChild(QFrame, "missionDeadlines").findChildren(FittedLabel, "missionDeadlineTitle")[1]
    assert name.text().endswith("…")
    assert (name.full_text(), name.toolTip()) == (title, title)
