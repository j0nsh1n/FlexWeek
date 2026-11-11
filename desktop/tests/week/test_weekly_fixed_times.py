"""A fixed time a student makes repeat every week, with an optional Until date: which weeks show it, where
Until cuts it, what turning the repeat off or changing Until does, and that every path that means "stands
in every week" treats it like School.

Dates (the one clock's week is Monday 2 November 2026): Tue 3 and Thu 5 Nov; the next weeks start Mon 9,
16, 23 and 30 Nov. Until Sat 14 Nov keeps Thu 12 Nov as the last one; Until Wed 11 Nov leaves Tue 10 only.
Driven through the light window's NativeSession, the layer the sheets write through."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import date, timedelta

import pytest
from PySide6.QtWidgets import QApplication

from desktop.native.calendar import is_setup_block, is_standing_block
from desktop.native.controller import NativeSession
from desktop.native.material.sheet_block import BlockDraft
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_pastnext import settled_session as settled
from desktop.tests.window_support import qapp  # noqa: F401

PIANO = {
    "id": "piano",
    "title": "Piano",
    "kind": "locked",
    "category": "extra",
    "start": "16:00",
    "duration_min": 60,
    "days": [1, 3],
}
SCHOOL = {
    "id": "school",
    "title": "School",
    "kind": "locked",
    "category": "class",
    "start": "08:30",
    "duration_min": 405,
    "days": [0, 1, 2, 3, 4],
}
FIRST_WEEK = "2026-11-02"


def week_after(weeks: int) -> str:
    return (date.fromisoformat(FIRST_WEEK) + timedelta(days=7 * weeks)).isoformat()


def go_to(qapp: QApplication, session: NativeSession, week: str) -> None:
    session.load_week(week)
    wait_until(qapp, lambda: session.week_start == week and not session.busy)
    settled(qapp, session)


def save_and_settle(qapp: QApplication, session: NativeSession) -> None:
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    settled(qapp, session)


def piano_days(session: NativeSession) -> list[int] | None:
    found = [b for b in session.blocks if b["title"] == "Piano"]
    assert len(found) <= 1, found
    return sorted(found[0]["days"]) if found else None


def piano_in(qapp: QApplication, session: NativeSession, weeks: int) -> list[int] | None:
    go_to(qapp, session, week_after(weeks))
    return piano_days(session)


def make_weekly(qapp: QApplication, session: NativeSession, until: str = "") -> dict:
    session.add_block(dict(PIANO), weekly=True, until=until)
    save_and_settle(qapp, session)
    return next(b for b in session.blocks if b["title"] == "Piano")


def test_a_weekly_block_shows_in_later_weeks_and_not_in_earlier_ones(qapp, window) -> None:
    session = window.session
    made = make_weekly(qapp, session)
    assert made["id"].startswith("weekly-")
    assert piano_in(qapp, session, 1) == [1, 3]
    assert piano_in(qapp, session, 2) == [1, 3]
    assert piano_in(qapp, session, 4) == [1, 3]
    assert piano_in(qapp, session, -1) is None


def test_until_saturday_keeps_thursday_the_last_day_and_the_week_after_has_none(qapp, window) -> None:
    session = window.session
    make_weekly(qapp, session, until="2026-11-14")
    assert piano_in(qapp, session, 1) == [1, 3]
    assert piano_in(qapp, session, 2) is None


def test_until_wednesday_leaves_only_tuesday_of_that_week(qapp, window) -> None:
    session = window.session
    make_weekly(qapp, session, until="2026-11-11")
    assert piano_in(qapp, session, 1) == [1]
    assert piano_in(qapp, session, 2) is None


def test_a_later_week_opened_before_does_not_keep_the_block_past_until(qapp, window) -> None:
    session = window.session
    make_weekly(qapp, session)
    go_to(qapp, session, week_after(2))
    gym = {"id": "gym", "title": "Gym", "kind": "locked", "start": "18:00", "duration_min": 60, "days": [2]}
    session.add_block(gym)
    save_and_settle(qapp, session)
    assert piano_days(session) == [1, 3]
    go_to(qapp, session, FIRST_WEEK)
    piano = next(b for b in session.blocks if b["title"] == "Piano")
    session.add_block(piano, weekly=True, until="2026-11-14")
    save_and_settle(qapp, session)
    assert piano_in(qapp, session, 2) is None
    assert [b["title"] for b in session.blocks] == ["Gym"]


def reload_week(qapp: QApplication, session: NativeSession) -> None:
    week = session.week_start
    go_to(qapp, session, week_after(5))
    go_to(qapp, session, week)


def test_an_until_inside_the_open_week_removes_the_later_days_of_that_week(qapp, window) -> None:
    session = window.session
    make_weekly(qapp, session, until="2026-11-03")
    reload_week(qapp, session)
    assert piano_days(session) == [1]
    assert piano_in(qapp, session, 1) is None


def test_changing_until_to_a_day_inside_the_open_week_cuts_that_week_too(qapp, window) -> None:
    session = window.session
    make_weekly(qapp, session)
    go_to(qapp, session, week_after(1))
    piano = next(b for b in session.blocks if b["title"] == "Piano")
    session.add_block(piano, weekly=True, until="2026-11-10")
    save_and_settle(qapp, session)
    reload_week(qapp, session)
    assert piano_days(session) == [1]
    assert piano_in(qapp, session, 2) is None
    assert piano_in(qapp, session, 0) == [1, 3]


def test_an_until_in_a_later_week_leaves_the_open_week_whole_and_cuts_that_week(qapp, window) -> None:
    session = window.session
    make_weekly(qapp, session)
    go_to(qapp, session, week_after(1))
    piano = next(b for b in session.blocks if b["title"] == "Piano")
    session.add_block(piano, weekly=True, until="2026-11-17")
    save_and_settle(qapp, session)
    reload_week(qapp, session)
    assert piano_days(session) == [1, 3]
    assert piano_in(qapp, session, 2) == [1]
    assert piano_in(qapp, session, 3) is None


def test_turning_the_repeat_off_keeps_this_week_and_ends_it_from_next_week(qapp, window) -> None:
    session = window.session
    made = make_weekly(qapp, session)
    session.add_block(made, weekly=False)
    save_and_settle(qapp, session)
    kept = next(b for b in session.blocks if b["title"] == "Piano")
    assert not is_standing_block(kept)
    assert kept["days"] == [1, 3]
    assert piano_in(qapp, session, 1) is None
    assert piano_in(qapp, session, 0) == [1, 3]


def test_changing_until_in_a_later_week_updates_the_block_from_that_week(qapp, window) -> None:
    session = window.session
    make_weekly(qapp, session)
    go_to(qapp, session, week_after(1))
    piano = next(b for b in session.blocks if b["title"] == "Piano")
    session.add_block(piano, weekly=True, until="2026-11-14")
    save_and_settle(qapp, session)
    assert piano_days(session) == [1, 3]
    assert piano_in(qapp, session, 2) is None
    assert piano_in(qapp, session, 0) == [1, 3]


def test_until_before_the_first_day_is_refused_in_words_and_changes_nothing(qapp, window) -> None:
    session = window.session
    refused = session.weekly_problem(dict(PIANO), "2026-11-02")
    assert refused == "Until can't be before the first day, Tue 3 Nov."
    assert session.weekly_problem(dict(PIANO), "2026-11-03") is None
    assert session.weekly_problem(dict(PIANO), "") is None
    session.add_block(dict(PIANO), weekly=True, until="2026-11-02")
    assert piano_days(session) is None
    assert session.dirty is False


def test_deleting_a_weekly_block_this_week_only_keeps_it_in_later_weeks(qapp, window) -> None:
    session = window.session
    make_weekly(qapp, session)
    go_to(qapp, session, week_after(1))
    session.delete_block(next(b["id"] for b in session.blocks if b["title"] == "Piano"))
    save_and_settle(qapp, session)
    assert next(b for b in session.blocks if b["title"] == "Piano")["missed_days"] == [1, 3]
    assert piano_in(qapp, session, 2) == [1, 3]


def test_deleting_a_weekly_block_this_week_and_later_ends_it_from_here(qapp, window) -> None:
    session = window.session
    make_weekly(qapp, session)
    go_to(qapp, session, week_after(1))
    session.delete_block(next(b["id"] for b in session.blocks if b["title"] == "Piano"), every_week=True)
    save_and_settle(qapp, session)
    assert piano_days(session) is None
    assert piano_in(qapp, session, 2) is None
    assert piano_in(qapp, session, 0) == [1, 3]


def test_running_setup_again_leaves_a_weekly_block_alone(qapp, window) -> None:
    session = window.session
    make_weekly(qapp, session)
    session.set_setup_blocks([dict(SCHOOL)])
    save_and_settle(qapp, session)
    assert sorted(b["title"] for b in session.blocks) == ["Piano", "School"]
    assert piano_in(qapp, session, 1) == [1, 3]
    go_to(qapp, session, FIRST_WEEK)
    session.set_setup_blocks([])
    save_and_settle(qapp, session)
    assert [b["title"] for b in session.blocks] == ["Piano"]
    assert piano_in(qapp, session, 1) == [1, 3]


def test_a_weekly_block_is_not_a_setup_block_but_stands_like_one() -> None:
    weekly = {**PIANO, "id": "weekly-abc"}
    assert is_standing_block(weekly) and not is_setup_block(weekly)
    assert is_standing_block(SCHOOL) and is_setup_block(SCHOOL)
    assert not is_standing_block(PIANO)


STANDING_IDS = ["school", "activity-1", "weekly-abc"]


@pytest.mark.parametrize("block_id", STANDING_IDS)
def test_every_path_that_means_stands_in_every_week_treats_these_ids_alike(
    qapp, window, block_id: str
) -> None:
    """The paths a student reaches a standing block by: taking it out of this week alone keeps it here
    missed, Delete in the Material sheet offers the three answers, and Copy last week leaves it out
    because it is already in every week."""
    session = window.session
    block = {**PIANO, "id": block_id}
    session.add_block(dict(block))
    save_and_settle(qapp, session)
    draft = BlockDraft(session, next(b for b in session.blocks if b["id"] == block_id), occurrence_day=1)
    draft.set("scope", "series")
    assert [a["id"] for a in draft.delete_question()["answers"]] == ["stay", "week", "every"]
    assert session._fixed_copy_rows({"blocks": [block]}) is None
    session.delete_block(block_id)
    assert next(b for b in session.blocks if b["id"] == block_id)["missed_days"] == [1, 3]
