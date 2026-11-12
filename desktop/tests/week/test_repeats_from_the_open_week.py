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

from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from desktop.native import window as window_module  # noqa: E402
from desktop.native.setup import WEEK  # noqa: E402
from desktop.native.widgets import SchoolHoursDialog  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import window  # noqa: E402,F401
from desktop.tests.sheets.support_material_sheets import bridge, material_week, snack  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
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
    """Run School hours the way the student does: it opens on what the window gives it, the end is
    moved, and it is accepted. Returns what the form showed."""
    seen: dict = {}

    def run(dialog: SchoolHoursDialog) -> QDialog.DialogCode:
        seen["days"] = dialog.days.days()
        seen["span"] = dialog.times.span()
        seen["line"] = dialog.this_week.text() if not dialog.this_week.isHidden() else None
        dialog.times.end.set_minutes(end_minutes)
        dialog.accept()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(window_module.SchoolHoursDialog, "exec", run)
    window._school_hours()
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


def test_p2_a_later_weeks_skipped_wednesday_stays_and_the_toast_names_that_week(
    qapp, window, after_setup, monkeypatch
) -> None:
    session = after_setup
    go_to(qapp, session, WEEK_AFTER)
    session.delete_block("school", scope="occurrence", day=WEDNESDAY)
    save_and_settle(qapp, session)
    go_to(qapp, session, NEXT_WEEK)
    school_hours(qapp, window, monkeypatch, 14 * 60 + 30)
    wait_until(qapp, lambda: "keeps its own change" in window.toast.text())
    assert window.toast.text() == (
        "School changed from this week on. The week of 16 Nov keeps its own change: no School on Wednesday."
    )
    assert not window.toast.button.isVisible()
    go_to(qapp, session, WEEK_AFTER)
    assert school_of(session) == ([0, 1, 3, 4], "08:30", 360, [])


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
    assert school_of(session) == ([0, 1, 2, 3, 4], "08:00", 405, [0, 1, 2, 3, 4])
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
    setup = window.setup_page
    assert [row.name.text() for row in setup.activities] == ["Soccer", "Saturday job"]
    setup._remove_activity(setup.activities[0])
    blocks = setup.week_blocks()
    assert [item["id"] for item in blocks] == ["school", "activity-2"]
    session.set_setup_blocks(blocks)
    save_and_settle(qapp, session)

    go_to(qapp, session, WEEK_AFTER)
    job = block(session, "activity-2")
    assert job is not None and (job["title"], job["missed_days"]) == ("Saturday job", [5])
    assert block(session, "activity-1") is None


def test_dragging_one_day_of_school_says_only_that_day_changed_and_undo_takes_it_back(
    qapp, window, after_setup
) -> None:
    session = after_setup
    go_to(qapp, session, NEXT_WEEK)
    window._move_block("school", WEDNESDAY, WEDNESDAY, 10 * 60, 12 * 60)
    wait_until(qapp, lambda: "Only this" in window.toast.text())
    assert window.toast.text().endswith(
        "Only this Wednesday changed. To change every week, open School hours."
    )
    assert window.toast.button.text().startswith("Undo")
    assert school_of(session)[0] == [0, 1, 3, 4]
    moved = [item for item in session.blocks if item["title"] == "School" and item["days"] == [WEDNESDAY]]
    assert [(item["start"], item["duration_min"]) for item in moved] == [("10:00", 120)]
    session.undo()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    assert school_of(session) == ([0, 1, 2, 3, 4], "08:30", 405, [])
    # Moved again and left: the week after still has its usual Wednesday. (Going to another week
    # ends this week's Undo, so this comes after it.)
    window._move_block("school", WEDNESDAY, WEDNESDAY, 10 * 60, 12 * 60)
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    go_to(qapp, session, WEEK_AFTER)
    assert school_of(session) == ([0, 1, 2, 3, 4], "08:30", 405, [])


def test_resizing_one_day_of_an_activity_points_to_setup(qapp, window, after_setup) -> None:
    session = after_setup
    go_to(qapp, session, NEXT_WEEK)
    window._move_block("activity-1", 3, 3, 16 * 60, 18 * 60)
    wait_until(qapp, lambda: "Only this" in window.toast.text())
    assert window.toast.text().endswith(
        "Only this Thursday changed. To change every week, run setup again from Settings."
    )
    go_to(qapp, session, WEEK_AFTER)
    soccer = block(session, "activity-1")
    assert soccer is not None and (soccer["days"], soccer["duration_min"]) == ([1, 3], 90)


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
