"""What the solver said has to reach the student.

spec.md: FlexWeek "explains in plain English every time something could not be placed or had to
move". The client took one explanation out of however many the solver gave, dropped it in the status
line, and never mentioned a move outside Running late.
"""

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
    from PySide6.QtWidgets import QApplication

    from desktop.native.widgets import PlanReview

WEEK = "2026-09-14"
TITLES = {"poster": "Science fair poster", "essay": "History essay", "chem": "Chem lab report"}
TRACE = {
    "placed": [{"id": "essay"}, {"id": "chem"}],
    "unplaced": [{"id": "poster", "title": "Science fair poster"}],
    "moves": [
        {
            "block_id": "essay",
            "reason": "RESHUFFLE_AFTER_MISS",
            "from_day": 3,
            "from_start": "18:45",
            "to_day": 4,
            "to_start": "10:00",
        }
    ],
    "explanations": [
        {
            "block_id": "poster",
            "reason": "DEADLINE_MISS",
            "message": "There is no slot left before this deadline.",
        },
        {
            "block_id": "chem",
            "message": "Very little room: scheduled to finish 29m before the deadline.",
            "slack_min": 29,
            "slack_status": "danger",
        },
        {
            "block_id": "essay",
            "message": "Room: scheduled to finish 5h before the deadline.",
            "slack_min": 300,
            "slack_status": "ok",
        },
    ],
}


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-plan-review-test"])
    yield application


def test_it_says_what_could_not_be_placed_and_why(qapp: QApplication) -> None:
    said = PlanReview().rows_for(TRACE, TITLES, WEEK)
    assert "Science fair poster has no time yet. There is no slot left before this deadline." in said


def test_it_says_what_moved_and_why(qapp: QApplication) -> None:
    said = PlanReview().rows_for(TRACE, TITLES, WEEK)
    moved = [line for line in said if "moved" in line]
    assert moved == [
        "History essay moved from Thu 18:45 to Fri 10:00."
        " Moved after a missed block so the rest of the week still fits."
    ]


def test_it_warns_about_a_tight_deadline_but_not_a_comfortable_one(qapp: QApplication) -> None:
    said = PlanReview().rows_for(TRACE, TITLES, WEEK)
    assert "Chem lab report: Very little room: scheduled to finish 29m before the deadline." in said
    assert not any("History essay: Room" in line for line in said)


def test_every_explanation_survives_not_just_the_first(qapp: QApplication) -> None:
    """The old status line showed notes[0] and dropped the rest."""
    assert len(PlanReview().rows_for(TRACE, TITLES, WEEK)) == 3


def test_a_clean_plan_says_nothing(qapp: QApplication) -> None:
    panel = PlanReview()
    panel.set_trace(
        {"placed": [{"id": "essay"}], "unplaced": [], "moves": [], "explanations": []}, TITLES, WEEK
    )
    assert panel.isVisible() is False
    assert panel.rows_for({"placed": [], "unplaced": [], "moves": [], "explanations": []}, TITLES, WEEK) == []


def test_the_panel_shows_the_count_and_can_be_dismissed(qapp: QApplication) -> None:
    from PySide6.QtWidgets import QPushButton

    panel = PlanReview()
    panel.show()
    panel.set_trace(TRACE, TITLES, WEEK)
    qapp.processEvents()
    assert panel.isVisible() is True
    assert panel.heading.text() == "Your plan: 2 placed, 1 without a time"
    assert panel.list.count() == 3
    seen: list[str] = []
    panel.dismissed.connect(lambda: seen.append("dismissed"))
    panel.findChild(QPushButton, "planReviewDismiss").click()
    assert seen == ["dismissed"] and panel.isVisible() is False


def test_an_unplaced_task_with_no_explanation_still_says_something(qapp: QApplication) -> None:
    bare = {
        "placed": [],
        "unplaced": [{"id": "poster", "title": "Science fair poster"}],
        "moves": [],
        "explanations": [],
    }
    assert PlanReview().rows_for(bare, TITLES, WEEK) == [
        "Science fair poster has no time yet. There was no room for it this week."
    ]


def test_a_block_that_never_moved_is_not_announced_as_moving(qapp: QApplication) -> None:
    """The solver records a move with no times for work that stayed unplaced. Said out loud that
    read "moved from no time to no time", under a line that had already explained the same block."""
    trace = {
        "placed": [],
        "unplaced": [{"id": "poster", "title": "Science fair poster"}],
        "moves": [
            {
                "block_id": "poster",
                "reason": "DEADLINE_MISS",
                "from_day": None,
                "from_start": None,
                "to_day": None,
                "to_start": None,
            }
        ],
        "explanations": [
            {
                "block_id": "poster",
                "reason": "DEADLINE_MISS",
                "message": "There is no slot left before this deadline.",
            }
        ],
    }
    said = PlanReview().rows_for(trace, TITLES, WEEK)
    assert said == ["Science fair poster has no time yet. There is no slot left before this deadline."]
    assert not any("no time to no time" in line for line in said)


def test_a_half_known_move_is_not_announced_either(qapp: QApplication) -> None:
    trace = {
        "placed": [{"id": "essay"}],
        "unplaced": [],
        "moves": [
            {
                "block_id": "essay",
                "reason": "NO_SLOT_LEFT",
                "from_day": 3,
                "from_start": "18:45",
                "to_day": None,
                "to_start": None,
            }
        ],
        "explanations": [],
    }
    assert PlanReview().rows_for(trace, TITLES, WEEK) == []


def test_the_box_is_as_tall_as_it_needs_and_no_taller(qapp: QApplication) -> None:
    """One line in a box four lines deep reads as an error."""
    one = PlanReview()
    one.show()
    one.set_trace(
        {
            "placed": [],
            "unplaced": [{"id": "poster", "title": "Science fair poster"}],
            "moves": [],
            "explanations": [],
        },
        TITLES,
        WEEK,
    )
    qapp.processEvents()
    many = PlanReview()
    many.show()
    many.set_trace(TRACE, TITLES, WEEK)
    qapp.processEvents()
    assert one.list.height() < many.list.height()
    assert many.list.height() <= 132
