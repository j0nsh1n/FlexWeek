"""School and Setup's activities changed from the open week, as the owner decided on 2026-11-12:

- School hours and Setup show the usual week (the repeat), with a line naming this week's own changes.
- A change from this week on leaves a later week's own change in place, and the student is told which
  week kept what, in the message area, without blocking.
- Dragging or resizing one day of a repeating block (or Move to day... in Material) changes that day
  only, with a note saying so, and Undo takes it back.

Real dates: the clock starts on Thursday 5 November 2026, so Setup runs in the week of 2 November and the
later weeks are 9, 16 and 23 November. Cases P1, P2, item 7 and item 10 are the design study's; each went
wrong before this change."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.setup_steps import WEEK  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import window  # noqa: E402,F401
from desktop.tests.sheets.support_material_sheets import bridge, material_week, snack  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.week.support_school_hours import school_hours as school_hours_form  # noqa: E402
from desktop.tests.week.test_standing_week import (  # noqa: E402,F401
    JOB,
    SCHOOL,
    SOCCER,
    after_setup,
    go_to,
    plus_weeks,
    save_and_settle,
)
from desktop.tests.window_support import qapp, settled  # noqa: E402,F401

WEDNESDAY = 2
SETUP_WEEK = "2026-11-02"
NEXT_WEEK = "2026-11-09"
WEEK_AFTER = "2026-11-16"
LATER_WEEK = "2026-11-23"


def block(session, block_id: str) -> dict | None:
    return next((item for item in session.blocks if item["id"] == block_id), None)


def school_of(session) -> tuple[list[int], str, int, list[int]]:
    school = block(session, "school")
    assert school is not None
    missed = list(school.get("missed_days") or [])
    return list(school["days"]), school["start"], school["duration_min"], missed


def school_hours(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch, end_minutes: int
) -> dict:
    """Change School's end from this week on, as Settings does. Returns what Setup's week page shows for
    School before the change: the usual days and span, and the line naming this week's own changes."""
    state = window._setup_state(first_run=False)
    usual = next(item for item in state.blocks if item["id"] == "school")
    seen = {
        "days": list(usual["days"]),
        "span": (usual["start"], usual["duration_min"]),
        "line": state.this_week or None,
    }
    school_hours_form(window, end_minutes)
    wait_until(qapp, lambda: not window.session.busy and not window.session.dirty)
    settled(qapp, window)
    return seen


def test_p1_school_hours_shows_the_usual_days_and_a_skipped_wednesday_stays_this_weeks(
    qapp, window, after_setup, monkeypatch
) -> None:
    session = after_setup
    go_to(qapp, session, NEXT_WEEK)
    session.delete_block("school", scope="occurrence", day=WEDNESDAY)
    save_and_settle(qapp, session)

    seen = school_hours(qapp, window, monkeypatch, 14 * 60 + 30)
    assert seen == {
        "days": [0, 1, 2, 3, 4],
        "span": ("08:30", 405),
        "line": "This week: no School on Wednesday.",
    }
    assert school_of(session) == ([0, 1, 3, 4], "08:30", 360, [])
    for later in (WEEK_AFTER, LATER_WEEK):
        go_to(qapp, session, later)
        assert school_of(session) == ([0, 1, 2, 3, 4], "08:30", 360, []), later


def test_undo_after_school_hours_takes_back_this_weeks_part_only(
    qapp, window, after_setup, monkeypatch
) -> None:
    session = after_setup
    go_to(qapp, session, NEXT_WEEK)
    school_hours(qapp, window, monkeypatch, 14 * 60 + 30)
    assert school_of(session) == ([0, 1, 2, 3, 4], "08:30", 360, [])
    session.undo()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    assert school_of(session) == ([0, 1, 2, 3, 4], "08:30", 405, [])
    go_to(qapp, session, WEEK_AFTER)
    assert school_of(session) == ([0, 1, 2, 3, 4], "08:30", 360, [])


def test_item7_setup_again_shows_the_usual_week_and_keeps_school_deleted_this_week_only(
    qapp, window, after_setup
) -> None:
    session = after_setup
    go_to(qapp, session, NEXT_WEEK)
    session.delete_block("school")
    save_and_settle(qapp, session)
    state = window._setup_state(first_run=False)
    assert [item["id"] for item in state.blocks] == ["school", "activity-1", "activity-2"]
    assert not any(item.get("missed_days") for item in state.blocks)
    assert state.this_week == "This week: no School that week."

    session.set_setup_blocks([{**SCHOOL, "start": "08:00"}, dict(SOCCER), dict(JOB)])
    save_and_settle(qapp, session)
    assert school_of(session) == ([0, 1, 2, 3, 4], "08:00", 405, [])
    assert block(session, "school")["removed_days"] == [0, 1, 2, 3, 4]
    go_to(qapp, session, WEEK_AFTER)
    assert school_of(session) == ([0, 1, 2, 3, 4], "08:00", 405, [])


def test_item10_removing_the_first_activity_in_setup_leaves_the_second_with_its_own_weeks(
    qapp, window, after_setup
) -> None:
    session = after_setup
    go_to(qapp, session, WEEK_AFTER)
    job = block(session, "activity-2")
    assert job is not None
    session.add_block({**job, "missed_days": [5]})  # no Saturday job that week
    save_and_settle(qapp, session)

    go_to(qapp, session, NEXT_WEEK)
    window._open_setup(WEEK, first_run=False)
    setup = window._account_bridge()
    assert [row["title"] for row in setup._activities] == ["Soccer", "Saturday job"]
    setup.removeActivity(0)
    blocks = setup._week_blocks()
    assert [item["id"] for item in blocks] == ["school", "activity-2"]
    session.set_setup_blocks(blocks)
    save_and_settle(qapp, session)

    go_to(qapp, session, WEEK_AFTER)
    job = block(session, "activity-2")
    assert job is not None and (job["title"], job["missed_days"]) == ("Saturday job", [5])
    assert block(session, "activity-1") is None


def material_with_school_repeating(qapp, window: NativeWindow):
    root = material_week(qapp, window)
    session = window.session
    school = block(session, "school")
    assert school is not None
    session.set_setup_blocks([school])
    session.save()
    settled(qapp, window)
    assert [item["id"] for item in session.repeats] == ["school"]
    return root


def test_material_move_to_day_on_school_says_only_that_day_changed(qapp, window) -> None:
    material_with_school_repeating(qapp, window)
    session = window.session
    # Friday is ahead of the clock (Thursday 19:00); Move to day... and a drop both land here.
    bridge(window).property("week").moveBlock("school", 4, 4, 9 * 60, 14 * 60 + 30)
    wait_until(qapp, lambda: "Only this" in snack(window))
    assert snack(window).endswith(
        "Only this Friday changed. To change every week, run setup again from Settings."
    )
    assert str(bridge(window).property("snackAction")) == "UNDO"
    assert block(session, "school")["days"] == [0, 1, 2, 3]
    session.undo()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    assert block(session, "school")["days"] == [0, 1, 2, 3, 4]


def test_material_says_which_later_week_kept_its_own_change(qapp, window) -> None:
    material_with_school_repeating(qapp, window)
    session = window.session
    go_to(qapp, session, NEXT_WEEK)
    session.delete_block("school", scope="occurrence", day=WEDNESDAY)
    save_and_settle(qapp, session)
    go_to(qapp, session, SETUP_WEEK)
    later = [{**item, "duration_min": 360} if item["id"] == "school" else item for item in session.repeats]
    session.change_repeats(later, "setting up your week")
    session.save()
    wait_until(qapp, lambda: "keeps its own change" in snack(window))
    assert snack(window) == (
        "School changed from this week on. The week of 9 Nov keeps its own change: no School on Wednesday."
    )
    assert str(bridge(window).property("snackAction")) == ""


def test_material_setup_shows_this_weeks_own_change(qapp, window) -> None:
    material_with_school_repeating(qapp, window)
    session = window.session
    session.delete_block("school", scope="occurrence", day=4)
    save_and_settle(qapp, session)
    window._open_setup(WEEK, first_run=False)
    account = bridge(window).property("account")
    assert account.property("schoolDays") == [0, 1, 2, 3, 4]
    assert account.property("thisWeek") == "This week: no School on Friday."


def answer_edited(window: NativeWindow, choice: str, seen: dict | None = None) -> None:
    """Answer the edited-weeks question on Material's prompt when it comes up, noting what it asked."""
    sheets = window._material_page.bridge.sheets
    tries = {"n": 0}

    def poll() -> None:
        tries["n"] += 1
        ask = dict(sheets.ask)
        if ask.get("id") != "edited-weeks":
            if tries["n"] < 400:
                QTimer.singleShot(5, poll)
            return
        if seen is not None:
            seen["body"] = ask["body"]
            seen["answers"] = [
                (a["id"], a["label"], a["kind"], bool(a.get("default"))) for a in ask["answers"]
            ]
        sheets.answer(choice)

    QTimer.singleShot(0, poll)


def test_p2_a_later_weeks_skipped_wednesday_stays_and_the_snackbar_names_that_week(
    qapp, window, after_setup, monkeypatch
) -> None:
    # The change reaches a week that has its own edit, so it asks. Except edited is today's behaviour.
    material_week(qapp, window)
    session = after_setup
    go_to(qapp, session, WEEK_AFTER)
    session.delete_block("school", scope="occurrence", day=WEDNESDAY)
    save_and_settle(qapp, session)
    go_to(qapp, session, NEXT_WEEK)
    answer_edited(window, "keep")
    school_hours(qapp, window, monkeypatch, 14 * 60 + 30)
    wait_until(qapp, lambda: "keeps its own change" in snack(window))
    assert snack(window) == (
        "School changed from this week on. The week of 16 Nov keeps its own change: no School on Wednesday."
    )
    assert str(bridge(window).property("snackAction")) == "", "later weeks have no Undo"


def test_material_dragging_one_day_of_school_says_only_that_day_changed_and_undo_takes_it_back(
    qapp, window, after_setup
) -> None:
    session = after_setup
    go_to(qapp, session, NEXT_WEEK)
    usual = school_of(session)
    material_week(qapp, window)
    this_week = school_of(session)
    week = bridge(window).property("week")
    week.moveBlock("school", WEDNESDAY, WEDNESDAY, 10 * 60, 12 * 60)
    wait_until(qapp, lambda: "Only this" in snack(window))
    assert snack(window).endswith(
        "Only this Wednesday changed. To change every week, run setup again from Settings."
    )
    assert str(bridge(window).property("snackAction")) == "UNDO"
    assert school_of(session)[0] == [0, 1, 3, 4]
    moved = [item for item in session.blocks if item["title"] == "School" and item["days"] == [WEDNESDAY]]
    assert [(item["start"], item["duration_min"]) for item in moved] == [("10:00", 120)]
    session.undo()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    assert school_of(session) == this_week
    # Moved again and left: the week after still has its usual Wednesday (the seed did not touch it).
    week.moveBlock("school", WEDNESDAY, WEDNESDAY, 10 * 60, 12 * 60)
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    go_to(qapp, session, WEEK_AFTER)
    assert school_of(session) == usual


def test_material_resizing_one_day_of_an_activity_points_to_setup(qapp, window, after_setup) -> None:
    session = after_setup
    go_to(qapp, session, NEXT_WEEK)
    material_week(qapp, window)
    bridge(window).property("week").moveBlock("activity-1", 3, 3, 16 * 60, 18 * 60)
    wait_until(qapp, lambda: "Only this" in snack(window))
    assert snack(window).endswith(
        "Only this Thursday changed. To change every week, run setup again from Settings."
    )
    go_to(qapp, session, WEEK_AFTER)
    soccer = block(session, "activity-1")
    assert soccer is not None and (soccer["days"], soccer["duration_min"]) == ([1, 3], 90)
