"""Homework left unfinished in a past week shows in More and in Plan, and Plan never moves it alone. Run on
the Material week, whose line above the grid carries "N left from last week" with Plan into this week and
Mark as finished.

The case: homework due Wednesday of week 2 whose only session is on Friday of week 1, never ticked;
week 2 is open at Monday 07:00."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import CLOCK
from desktop.native.material.bridge_sheets import NOTHING_UNFINISHED as NONE_UNFINISHED
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import pump, show_material
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_material import _click, _qml
from desktop.tests.week.support_pastnext import FRIDAY, WEDNESDAY, classic_week
from desktop.tests.window_support import qapp, settled  # noqa: F401

PLAN_IT = "leftOverPlan"
FINISHED = "leftOverDone"


def left_in_week_one(qapp: QApplication, window: NativeWindow) -> tuple[str, str]:
    """Week 1 (the open week): the Lab report, due Wednesday of week 2, its one session on Friday 16:00
    of week 1, not ticked. Then the clock moves to Monday 07:00 of week 2 and week 2 is opened.
    Returns (week 1, week 2)."""
    classic_week(qapp, window)
    session = window.session
    week1 = session.week_start
    week2 = (date.fromisoformat(week1) + timedelta(days=7)).isoformat()
    due = (date.fromisoformat(week2) + timedelta(days=WEDNESDAY)).isoformat() + "T23:59"
    session.add_homework({"id": "lab", "title": "Lab report", "due": due, "estimate_min": 60, "revision": 0})
    session.save()
    settled(qapp, window)
    block = next(b for b in session.blocks if b.get("assignment_id") == "lab")
    assert session.hand_move(block["id"], -1, FRIDAY, 16 * 60, 17 * 60)
    session.save()
    settled(qapp, window)
    CLOCK.set(datetime.fromisoformat(week2) + timedelta(hours=7))
    session.load_week(week2)
    wait_until(qapp, lambda: session.week_start == week2 and not session.busy)
    settled(qapp, window)
    return week1, week2


def more_unfinished_row(window: NativeWindow) -> tuple[bool, str]:
    show_material(QApplication.instance(), window)
    bridge = window._material_page.bridge
    bridge.openMore()
    row = next(item for item in bridge.sheets.moreEntries if item["id"] == "unfinishedOpen")
    bridge.sheets.forceClose()
    return bool(row["enabled"]), f"{row['label']} {row['detail']}"


def lab_sessions(window: NativeWindow) -> list[dict]:
    return [b for b in window.session.blocks if b.get("assignment_id") == "lab"]


def visible_button(window: NativeWindow, name: str):
    """Material's button of this object name when its row is showing, else None."""
    pump(QApplication.instance(), 10)
    button = _qml(show_material(QApplication.instance(), window), name)
    return button if button.property("visible") else None


def chip_words(window: NativeWindow) -> str:
    pump(QApplication.instance(), 10)
    return str(_qml(show_material(QApplication.instance(), window), "leftOverWords").property("text"))


def press(window: NativeWindow, button) -> None:
    _click(window, button)


def plan(qapp: QApplication, window: NativeWindow) -> None:
    window.session.solve()
    wait_until(qapp, lambda: not window.session.planning and not window.session.busy)
    settled(qapp, window)


def test_more_counts_the_session_left_in_last_week(qapp, window) -> None:
    left_in_week_one(qapp, window)
    enabled, words = more_unfinished_row(window)
    assert enabled and NONE_UNFINISHED not in words and "1" in words, words


def test_plan_never_moves_last_weeks_session_on_its_own(qapp, window) -> None:
    left_in_week_one(qapp, window)
    plan(qapp, window)
    assert [b for b in lab_sessions(window) if b.get("start")] == []


def test_plan_shows_the_unfinished_from_last_week_chip(qapp, window) -> None:
    left_in_week_one(qapp, window)
    plan(qapp, window)
    assert chip_words(window) == "1 left from last week"
    assert visible_button(window, PLAN_IT) and visible_button(window, FINISHED)


def test_plan_them_places_it_in_week_two_before_wednesday(qapp, window) -> None:
    left_in_week_one(qapp, window)
    plan(qapp, window)
    button = visible_button(window, PLAN_IT)
    assert button is not None, f"no {PLAN_IT}"
    press(window, button)
    settled(qapp, window)
    placed = [b for b in lab_sessions(window) if b.get("start")]
    assert placed and all(b["days"][0] < WEDNESDAY or b["days"] == [WEDNESDAY] for b in placed), placed


def test_marking_it_finished_empties_more_and_plan_places_nothing(qapp, window) -> None:
    left_in_week_one(qapp, window)
    plan(qapp, window)
    button = visible_button(window, FINISHED)
    assert button is not None, f"no {FINISHED}"
    press(window, button)
    settled(qapp, window)
    enabled, words = more_unfinished_row(window)
    assert not enabled and NONE_UNFINISHED in words
    plan(qapp, window)
    assert [b for b in lab_sessions(window) if b.get("start")] == []




def test_the_past_week_tag_survives_editing_the_assignment(qapp, window) -> None:
    left_in_week_one(qapp, window)
    session = window.session
    session.add_homework({**session.assignments["lab"], "title": "Updated lab report"})
    session.save()
    settled(qapp, window)
    item = next(item for item in session.unfinished() if item["id"] == "lab")
    assert item["left_over_state"] == "left_from_last_week"


def test_time_already_planned_this_week_is_not_left_from_last_week(qapp, window) -> None:
    """Last week's hour was never done, but the same hour now has a time on Tuesday: nothing is left
    over, so there is no line and no Plan into this week to press (audit F-009)."""
    left_in_week_one(qapp, window)
    session = window.session
    assert [item["id"] for item in session.unfinished()] == ["lab"]
    session.add_block(
        {
            "id": "lab-again",
            "title": "Lab report",
            "kind": "flexible",
            "assignment_id": "lab",
            "duration_min": 60,
            "days": [1],
            "start": "15:00",
        }
    )
    session.save()
    settled(qapp, window)
    assert session.unfinished() == []
    plan(qapp, window)
    assert "left from last week" not in chip_words(window)
    assert visible_button(window, PLAN_IT) is None


def test_the_line_shows_only_the_minutes_that_still_have_no_time(qapp, window) -> None:
    """The lab report is 60 minutes and none of it is done. Half an hour of it now has a time this
    week, so the line is for the other 30 and Plan into this week places those 30."""
    left_in_week_one(qapp, window)
    session = window.session
    session.add_block(
        {
            "id": "lab-half",
            "title": "Lab report",
            "kind": "flexible",
            "assignment_id": "lab",
            "duration_min": 30,
            "days": [1],
            "start": "15:00",
        }
    )
    session.save()
    settled(qapp, window)
    assert [(item["id"], item["remaining_min"]) for item in session.unfinished()] == [("lab", 30)]
    plan(qapp, window)
    button = visible_button(window, PLAN_IT)
    assert button is not None, f"no {PLAN_IT}"
    press(window, button)
    settled(qapp, window)
    new_hours = [b for b in lab_sessions(window) if b["id"] != "lab-half" and b["duration_min"] == 30]
    assert new_hours, lab_sessions(window)


def test_plan_into_this_week_places_the_hour_this_week_already_holds_without_a_time(qapp, window) -> None:
    """The line lists minutes that have no time, a session waiting for one included, and pressing Plan
    into this week gives that session its time instead of saying the homework is fully planned."""
    left_in_week_one(qapp, window)
    session = window.session
    session.add_block(
        {
            "id": "lab-waiting",
            "title": "Lab report",
            "kind": "flexible",
            "assignment_id": "lab",
            "duration_min": 60,
            "days": [0, 1, 2],
        }
    )
    session.save()
    settled(qapp, window)
    assert [(item["id"], item["remaining_min"]) for item in session.unfinished()] == [("lab", 60)]
    button = visible_button(window, PLAN_IT)
    assert button is not None, f"no {PLAN_IT}"
    press(window, button)
    settled(qapp, window)
    assert [b for b in lab_sessions(window) if b.get("start")], lab_sessions(window)
    assert "fully planned" not in session.message, session.message


def hold_a_session(window: NativeWindow, start: str | None, *, pinned: bool = False) -> None:
    """A second Lab report hour in week 2: Monday at `start`, or waiting for a time when None."""
    block = {
        "id": "lab-monday",
        "title": "Lab report",
        "kind": "flexible",
        "assignment_id": "lab",
        "duration_min": 60,
        "days": [0],
    }
    if start is not None:
        block["start"] = start
        block["pinned"] = pinned
    window.session.add_block(block)
    window.session.save()


def press_plan_into_this_week(qapp: QApplication, window: NativeWindow) -> None:
    window.session.week_changed.emit()
    settled(qapp, window)
    button = visible_button(window, PLAN_IT)
    assert button is not None, f"no {PLAN_IT}"
    press(window, button)
    wait_until(qapp, lambda: not window.session.planning and not window.session.busy)
    settled(qapp, window)


def test_plan_into_this_week_moves_a_missed_session_the_line_lists(qapp, window) -> None:
    """The hour planned for Monday 08:00 was not done and it is now 10:00. The line counts it as time
    with no time, so Plan into this week moves it to a time ahead and does not say it has a time."""
    _week1, week2 = left_in_week_one(qapp, window)
    hold_a_session(window, "08:00")
    settled(qapp, window)
    CLOCK.set(datetime.fromisoformat(week2) + timedelta(hours=10))
    assert [(item["id"], item["remaining_min"]) for item in window.session.unfinished()] == [("lab", 60)]
    press_plan_into_this_week(qapp, window)
    moved = next(b for b in lab_sessions(window) if b["id"] == "lab-monday")
    assert (moved["days"][0], moved["start"]) > (0, "10:00"), moved
    assert "already has a time" not in window.session.message


def test_plan_into_this_week_leaves_a_pinned_missed_session_where_it_is(qapp, window) -> None:
    """A session the student pinned is never moved, so the line has nothing to offer for it."""
    _week1, week2 = left_in_week_one(qapp, window)
    hold_a_session(window, "08:00", pinned=True)
    settled(qapp, window)
    CLOCK.set(datetime.fromisoformat(week2) + timedelta(hours=10))
    window.session.week_changed.emit()
    settled(qapp, window)
    window.session.plan_left(["lab"])
    wait_until(qapp, lambda: not window.session.planning and not window.session.busy)
    settled(qapp, window)
    pinned = next(b for b in lab_sessions(window) if b["id"] == "lab-monday")
    assert (pinned["days"], pinned["start"]) == ([0], "08:00")


def test_the_panels_plan_button_places_a_session_that_is_waiting_for_a_time(qapp, window) -> None:
    """In the Overdue and left from last week panel, Plan into this week on one homework gives its
    waiting session a time instead of saying the homework is fully planned."""
    left_in_week_one(qapp, window)
    hold_a_session(window, None)
    settled(qapp, window)
    window._plan_unfinished("lab")
    wait_until(qapp, lambda: not window.session.planning and not window.session.busy)
    settled(qapp, window)
    assert [b for b in lab_sessions(window) if b["id"] == "lab-monday" and b.get("start")]
    assert "fully planned" not in window.session.message


def add_done_hour(window: NativeWindow, block_id: str, day: int) -> None:
    """An hour of the lab report already ticked done, on `day` of the open week."""
    window.session.add_block(
        {
            "id": block_id,
            "title": "Lab report",
            "kind": "flexible",
            "assignment_id": "lab",
            "duration_min": 60,
            "days": [day],
            "start": "06:00",
            "completed": True,
            "completed_day": day,
        }
    )


def test_a_session_ticked_done_this_week_is_one_credit_in_the_line_the_count_and_plan(qapp, window) -> None:
    """A 2 h lab report with an hour ticked done this week has 1 h left: the line, "needs a time" and
    Plan into this week all say 60 (before, the count said 120 and Plan placed 120)."""
    left_in_week_one(qapp, window)
    session = window.session
    session.assignments["lab"]["estimate_min"] = 120
    session.dirty_assignments.add("lab")
    add_done_hour(window, "lab-done", 0)
    session.save()
    settled(qapp, window)
    assert [(item["id"], item["remaining_min"]) for item in session.unfinished()] == [("lab", 60)]
    assert [row["minutes"] for row in session.homework_time_needed()] == [60]
    press_plan_into_this_week(qapp, window)
    placed = sum(b["duration_min"] for b in lab_sessions(window) if b.get("start") and not b.get("completed"))
    assert placed == 60, lab_sessions(window)


def test_an_hour_ticked_done_in_an_earlier_saved_week_leaves_nothing_to_carry(qapp, window) -> None:
    """The lab report's only session was ticked done last week: no line, nothing needed this week."""
    week1, week2 = left_in_week_one(qapp, window)
    session = window.session
    session.load_week(week1)
    wait_until(qapp, lambda: session.week_start == week1 and not session.busy)
    settled(qapp, window)
    old = lab_sessions(window)[0]
    day = old["days"][0]
    session.add_block({**old, "start": "06:00", "pinned": False, "completed": True, "completed_day": day})
    session.save()
    settled(qapp, window)
    session.load_week(week2)
    wait_until(qapp, lambda: session.week_start == week2 and not session.busy)
    settled(qapp, window)
    assert session.unfinished() == []
    assert session.homework_time_needed() == []
