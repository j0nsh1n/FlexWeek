"""The week model is the one reading of the week every layout shares, so it is held to two things:
the placement rules written out as literal cases, and agreement with what the week table draws.
"""

from __future__ import annotations

import importlib.util
import os

import pytest

from desktop.native.weekmodel import build_week, clock_label, due_label, length_label

WEEK = "2026-09-14"
HOMEWORK = {
    "chem": {"id": "chem", "title": "Chem lab report", "due": "2026-09-17T23:59", "completed": False},
    "essay": {"id": "essay", "title": "History essay", "due": "2026-09-18T21:00", "completed": False},
    "poster": {"id": "poster", "title": "Science fair poster", "due": "2026-09-20T20:00", "completed": False},
    "math": {"id": "math", "title": "Math worksheet", "due": "2026-09-15T08:00", "completed": True},
}


def block(
    block_id: str, kind: str, days: list[int], start: str | None, minutes: int, **extra: object
) -> dict:
    return {
        "id": block_id,
        "title": extra.pop("title", block_id.title()),
        "kind": kind,
        "category": extra.pop("category", "class" if kind == "locked" else "assignments"),
        "days": days,
        "start": start,
        "duration_min": minutes,
        **extra,
    }


BLOCKS = [
    block("school", "locked", [0, 1, 2, 3, 4], "08:00", 390),
    block("dinner", "locked", [0, 1, 2, 3, 4, 5, 6], "18:00", 30, category="meals"),
    block("chem-1", "flexible", [3], None, 90, assignment_id="chem"),
    block("essay-1", "flexible", [3], "18:45", 60, assignment_id="essay"),
    block("poster-1", "flexible", [], None, 120, assignment_id="poster"),
    block("math-1", "flexible", [0, 1], "15:45", 45, assignment_id="math", completed=True, completed_day=0),
]
TRACE = {
    "placed": [block("chem-1", "flexible", [3], "20:00", 90, assignment_id="chem")],
    "unplaced": [block("poster-1", "flexible", [], None, 120, assignment_id="poster")],
    "explanations": [
        {"block_id": "chem-1", "message": "Very little room.", "slack_min": 149, "slack_status": "danger"},
        {"block_id": "essay-1", "message": "Limited room.", "slack_min": 1515, "slack_status": "tight"},
        {
            "block_id": "poster-1",
            "message": "There is no slot left before this deadline.",
            "reason": "DEADLINE_MISS",
        },
    ],
}


def thursday() -> list[tuple[str, str, str]]:
    week = build_week(WEEK, BLOCKS, HOMEWORK, TRACE)
    return [(item.block_id, clock_label(item.start), clock_label(item.end)) for item in week.on_day(3)]


def test_the_solver_placement_gives_unscheduled_work_its_time() -> None:
    assert thursday() == [
        ("school", "08:00", "14:30"),
        ("dinner", "18:00", "18:30"),
        ("essay-1", "18:45", "19:45"),
        ("chem-1", "20:00", "21:30"),
    ]


def test_a_finished_session_stays_on_the_day_it_was_finished() -> None:
    week = build_week(WEEK, BLOCKS, HOMEWORK, TRACE)
    math = [(item.day, item.done) for item in week.occurrences if item.block_id == "math-1"]
    assert math == [(0, True)]


def test_a_solver_placement_never_moves_finished_work() -> None:
    moved = {**TRACE, "placed": [*TRACE["placed"], block("math-1", "flexible", [4], "10:00", 45)]}
    week = build_week(WEEK, BLOCKS, HOMEWORK, moved)
    assert [
        (item.day, clock_label(item.start)) for item in week.occurrences if item.block_id == "math-1"
    ] == [(0, "15:45")]


def test_work_with_no_time_waits_with_the_solvers_reason() -> None:
    week = build_week(WEEK, BLOCKS, HOMEWORK, TRACE)
    assert [(item.title, item.minutes, item.reason) for item in week.waiting] == [
        ("Poster-1", 120, "There is no slot left before this deadline.")
    ]


def test_work_nobody_has_planned_yet_says_so() -> None:
    week = build_week(WEEK, BLOCKS, HOMEWORK, None)
    assert [(item.block_id, item.reason) for item in week.waiting] == [
        ("chem-1", "Not planned yet."),
        ("poster-1", "Not planned yet."),
    ]


def test_risk_is_the_solvers_verdict_and_the_most_squeezed_comes_first() -> None:
    week = build_week(WEEK, BLOCKS, HOMEWORK, TRACE)
    assert [(item.block_id, item.slack, item.slack_words) for item in week.open_work()] == [
        ("chem-1", "danger", "Very little room"),
        ("essay-1", "tight", "Limited room"),
    ]


def test_without_a_verdict_no_risk_is_claimed() -> None:
    week = build_week(WEEK, BLOCKS, HOMEWORK, None)
    assert [(item.block_id, item.slack, item.slack_words) for item in week.open_work()] == [
        ("essay-1", None, "")
    ]


def test_load_counts_homework_minutes_only() -> None:
    week = build_week(WEEK, BLOCKS, HOMEWORK, TRACE)
    assert [week.load_min(day) for day in range(7)] == [45, 0, 0, 150, 0, 0, 0]


def test_the_day_queue_is_what_is_on_now_then_the_rest_in_order() -> None:
    week = build_week(WEEK, BLOCKS, HOMEWORK, TRACE)
    lunch = week.day_queue(3, 13 * 60 + 40)
    assert lunch.current is not None and lunch.current.block_id == "school"
    assert [item.block_id for item in lunch.queue] == ["school", "dinner", "essay-1", "chem-1"]
    evening = week.day_queue(3, 19 * 60)
    assert evening.current is not None and evening.current.block_id == "essay-1"
    assert [item.block_id for item in evening.queue] == ["essay-1", "chem-1"]
    night = week.day_queue(3, 22 * 60)
    assert night.current is None and night.queue == ()


def test_homework_wins_over_the_fixed_block_around_it() -> None:
    blocks = [*BLOCKS, block("study-hall", "flexible", [3], "10:00", 30, assignment_id="essay")]
    week = build_week(WEEK, blocks, HOMEWORK, TRACE)
    current = week.day_queue(3, 10 * 60 + 10).current
    assert current is not None and current.block_id == "study-hall"


def test_finished_and_missed_homework_leave_the_queue() -> None:
    blocks = [
        block("essay-1", "flexible", [3], "18:45", 60, assignment_id="essay", missed_days=[3]),
        block("chem-1", "flexible", [3], "20:00", 90, assignment_id="chem", completed=True),
    ]
    week = build_week(WEEK, blocks, HOMEWORK, None)
    assert week.day_queue(3, 18 * 60).queue == ()
    assert [(item.block_id, item.missed, item.done) for item in week.on_day(3)] == [
        ("essay-1", True, False),
        ("chem-1", False, True),
    ]


def test_homework_the_account_marks_complete_is_done_even_if_the_block_is_not() -> None:
    blocks = [block("math-2", "flexible", [2], "16:00", 30, assignment_id="math")]
    week = build_week(WEEK, blocks, HOMEWORK, None)
    assert [(item.block_id, item.done) for item in week.occurrences] == [("math-2", True)]


def test_a_block_cannot_run_past_midnight() -> None:
    week = build_week(WEEK, [block("late", "locked", [0], "23:30", 90)], {}, None)
    assert [(clock_label(item.start), clock_label(item.end)) for item in week.occurrences] == [
        ("23:30", "24:00")
    ]


def test_labels_read_the_way_a_student_says_them() -> None:
    assert [length_label(value) for value in (30, 60, 90, 0)] == ["30 min", "1 h", "1 h 30 min", "0 min"]
    assert due_label("2026-09-17T23:59", WEEK) == "Thu 23:59"
    assert due_label("2026-09-28T08:00", WEEK) == "Sep 28 08:00"
    assert due_label("2026-09-20", WEEK) == "Sun"
    assert due_label(None, WEEK) == ""


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent")
def test_the_model_places_every_block_where_the_week_table_draws_it() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from desktop.native.widgets import ENDS_ROLE, WeekTable, hhmm_to_slot

    app = QApplication.instance() or QApplication(["flexweek-weekmodel-test"])
    table = WeekTable()
    table.set_week(WEEK, BLOCKS, TRACE)
    drawn = set()
    for row in range(table.rowCount()):
        for day in range(table.columnCount()):
            item = table.item(row, day)
            if item is not None and item.data(ENDS_ROLE)[0]:
                drawn.update((block_id, day, row) for block_id in item.data(Qt.ItemDataRole.UserRole))
    week = build_week(WEEK, BLOCKS, HOMEWORK, TRACE)
    modelled = {(item.block_id, item.day, hhmm_to_slot(clock_label(item.start))) for item in week.occurrences}
    assert modelled == drawn
    assert len(drawn) == 15
    del app
