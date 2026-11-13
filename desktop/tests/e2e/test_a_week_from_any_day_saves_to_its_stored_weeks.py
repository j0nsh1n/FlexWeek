"""A week on screen that starts on Wednesday (or Sunday) holds the seven days from that day, and what
the student saves lands in the stored (Monday) week of each day. The shared clock is Thursday
5 November 2026: from Wednesday that week runs Wednesday 4 to Tuesday 10 November, which covers the
stored weeks of Monday 2 and Monday 9 November; from Sunday it runs Sunday 1 to Saturday 7 November."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from desktop.native import widgets
from desktop.native.calendar import SETUP_SCHOOL_ID
from desktop.native.client import ApiError
from desktop.native.controller import NativeSession
from desktop.native.widgets import BlockDialog
from desktop.server import LocalServer
from desktop.tests.e2e.account_sessions import HASHING_WAIT, HELD, server  # noqa: F401
from desktop.tests.e2e.saved_weeks import read_week
from desktop.tests.logic_support import essay, fixed, settled
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import PASSWORD, host, qapp  # noqa: F401

WEDNESDAY = 2
SUNDAY = 6


def signed_in_from(qapp: QApplication, origin: str, username: str, first_weekday: int) -> NativeSession:
    session = NativeSession(origin, qapp)
    HELD.append(session)
    session.follow_first_weekday(first_weekday)
    session.register(username, PASSWORD)
    wait_until(qapp, lambda: session.account is not None, HASHING_WAIT)
    session.finish_recovery()
    wait_until(qapp, lambda: session.account is not None and not session.busy, HASHING_WAIT)
    settled(qapp, session)
    return session


def days_by_id(week: dict) -> dict[str, list[int]]:
    return {block["id"]: block["days"] for block in week["blocks"]}


def test_the_open_week_starts_on_the_chosen_day_and_holds_today(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in_from(qapp, server.origin, "wednesday", WEDNESDAY)
    assert session.week_start == "2026-11-04"
    assert session.today_column("2026-11-05") == 1
    assert session.today_column("2026-11-10") == 6
    assert session.today_column("2026-11-11") is None
    sunday = signed_in_from(qapp, server.origin, "sunday", SUNDAY)
    assert sunday.week_start == "2026-11-01"
    assert sunday.today_column("2026-11-05") == 4


def test_a_block_on_monday_after_the_seam_is_stored_in_that_mondays_week(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in_from(qapp, server.origin, "seam", WEDNESDAY)
    # Shown day 5 is Monday 9 November; shown day 1 is Thursday 5 November.
    session.add_block(fixed("mon9", "Club", 5, "16:00"))
    session.add_block(fixed("thu5", "Piano", 1, "17:00"))
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty and session.pending_save is None)
    assert days_by_id(read_week(qapp, session, "2026-11-09")) == {"mon9": [0]}
    assert days_by_id(read_week(qapp, session, "2026-11-02")) == {"thu5": [3]}
    assert session.revision == [1, 1]
    assert {block["id"]: block["days"] for block in session.blocks} == {"thu5": [1], "mon9": [5]}


def test_undo_and_redo_across_the_seam_go_back_to_each_stored_week(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in_from(qapp, server.origin, "undo", WEDNESDAY)
    session.add_block(fixed("mon9", "Club", 5, "16:00"))
    session.save()
    wait_until(qapp, lambda: not session.busy and session.pending_save is None)
    assert session.can_undo()
    session.undo()
    wait_until(qapp, lambda: not session.busy and session.pending_save is None)
    settled(qapp, session)
    assert session.blocks == []
    assert read_week(qapp, session, "2026-11-09")["blocks"] == []
    session.redo()
    wait_until(qapp, lambda: not session.busy and session.pending_save is None)
    settled(qapp, session)
    assert days_by_id(read_week(qapp, session, "2026-11-09")) == {"mon9": [0]}
    assert read_week(qapp, session, "2026-11-02")["blocks"] == []


def test_a_failed_save_retried_lands_once_in_each_stored_week(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in_from(qapp, server.origin, "retry", WEDNESDAY)
    held: list = []
    original = session.client.request

    def hold(method, path, body, ok, fail):  # type: ignore[no-untyped-def]
        if method == "POST" and path == "/api/changes":
            held.append((method, path, body, ok, fail))
        else:
            original(method, path, body, ok, fail)

    session.client.request = hold  # type: ignore[method-assign]
    try:
        session.add_block(fixed("mon9", "Club", 5, "16:00"))
        session.add_block(fixed("fri6", "Swim", 2, "07:00"))
        session.save()
        first_body = held[0][2]
        held.pop(0)[4](ApiError(503, "The planner is unavailable."))
        qapp.processEvents()
        assert session.pending_save is not None
        session.retry_save()
        wait_until(qapp, lambda: len(held) >= 1)
        assert held[0][2] == first_body
        original(*held.pop(0))
        wait_until(qapp, lambda: not session.busy and session.pending_save is None)
    finally:
        session.client.request = original  # type: ignore[method-assign]
    session.reload()
    settled(qapp, session)
    assert days_by_id(read_week(qapp, session, "2026-11-09")) == {"mon9": [0]}
    assert days_by_id(read_week(qapp, session, "2026-11-02")) == {"fri6": [4]}
    assert read_week(qapp, session, "2026-11-02")["revision"] == 1
    assert read_week(qapp, session, "2026-11-09")["revision"] == 1


def test_next_and_previous_move_by_seven_days_and_a_day_opens_the_week_that_holds_it(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in_from(qapp, server.origin, "travel", WEDNESDAY)
    session.load_week("2026-11-11")
    settled(qapp, session)
    assert session.week_start == "2026-11-11"
    # Any date opens the week that holds it: Today passes today's date, Thursday 5 November.
    session.load_week("2026-11-05")
    settled(qapp, session)
    assert session.week_start == "2026-11-04"
    session.load_week("2026-11-11")
    settled(qapp, session)
    # Tuesday 17 November belongs to the week that began on Wednesday 11.
    session.open_day("2026-11-17")
    settled(qapp, session)
    assert session.week_start == "2026-11-11"
    assert session.selected_day == "2026-11-17"
    # Monday 30 November is in the week from Wednesday 25, over the month end.
    session.open_day("2026-11-30")
    settled(qapp, session)
    assert session.week_start == "2026-11-25"


def test_changing_the_first_day_reopens_the_week_holding_the_selected_day(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in_from(qapp, server.origin, "follow", 0)
    assert session.week_start == "2026-11-02"
    session.follow_first_weekday(WEDNESDAY)
    settled(qapp, session)
    assert session.week_start == "2026-11-04"
    session.follow_first_weekday(SUNDAY)
    settled(qapp, session)
    assert session.week_start == "2026-11-01"


def essay_sessions(blocks: list[dict]) -> list[tuple[int, str, int]]:
    return sorted(
        (block["days"][0], block["start"], block["duration_min"])
        for block in blocks
        if block.get("assignment_id") == "essay" and block.get("start")
    )


def test_plan_and_replan_all_plan_the_week_on_screen_and_store_each_session_once(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in_from(qapp, server.origin, "plan", WEDNESDAY)
    # Homework added with no date is due at the end of the week on screen: Tuesday 10, 11:59 PM.
    homework = essay(session, 180)
    assert homework["due"] == "2026-11-10T23:59"
    session.add_homework(homework)
    # Thursday 5 to Sunday 8 (days 1 to 4) are full, so the essay has to go after the Monday seam.
    away = {"id": "busy", "title": "Away", "kind": "locked", "start": "00:00", "duration_min": 1440}
    session.add_block({**away, "days": [1, 2, 3, 4]})
    session.save()
    wait_until(qapp, lambda: not session.busy and session.pending_save is None)
    for everything in (False, True):
        session.solve(everything=everything)
        wait_until(qapp, lambda: not session.busy and not session.planning and session.pending_save is None)
        settled(qapp, session)
        shown = essay_sessions(session.blocks)
        assert sum(minutes for *_, minutes in shown) == 180, session.message
        # Monday 9 and Tuesday 10, the last days of the week on screen.
        assert {day for day, *_ in shown} <= {5, 6}, shown
        assert essay_sessions(read_week(qapp, session, "2026-11-02")["blocks"]) == []
        stored = essay_sessions(read_week(qapp, session, "2026-11-09")["blocks"])
        assert [(day + 5, start, minutes) for day, start, minutes in stored] == shown
        assert essay_sessions(read_week(qapp, session, "2026-11-16")["blocks"]) == []


def school_days(week: dict) -> list[int]:
    return next((block["days"] for block in week["blocks"] if block["id"] == SETUP_SCHOOL_ID), [])


def test_school_changed_from_a_wednesday_week_on_keeps_its_weekdays_and_the_days_before(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in_from(qapp, server.origin, "school", WEDNESDAY)
    school = {"id": SETUP_SCHOOL_ID, "title": "School", "kind": "locked", "category": "class",
              "start": "08:30", "duration_min": 390, "days": [0, 1, 2, 3, 4]}  # fmt: skip
    session.set_setup_blocks([school])
    session.save()
    wait_until(qapp, lambda: not session.busy and session.pending_save is None)
    # Monday to Friday: Wednesday 4, Thursday 5, Friday 6, Monday 9 and Tuesday 10 of the week on screen.
    assert school_days({"blocks": session.blocks}) == [0, 1, 2, 5, 6]
    # From this week on, no School on Fridays: the week on screen and every week after it.
    session.set_setup_blocks([{**school, "days": [0, 1, 2, 3]}])
    session.save()
    wait_until(qapp, lambda: not session.busy and session.pending_save is None)
    settled(qapp, session)
    assert school_days({"blocks": session.blocks}) == [0, 1, 5, 6]
    # Monday 2 and Tuesday 3 come before the week on screen: School started on Wednesday 4.
    assert school_days(read_week(qapp, session, "2026-11-02")) == [2, 3]
    assert school_days(read_week(qapp, session, "2026-11-09")) == [0, 1, 2, 3]
    assert school_days(read_week(qapp, session, "2026-11-16")) == [0, 1, 2, 3]
    assert school_days(read_week(qapp, session, "2026-10-26")) == []


def test_a_routine_saved_in_a_wednesday_week_keeps_its_weekdays(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in_from(qapp, server.origin, "routine", WEDNESDAY)
    # Day 5 of the week from Wednesday 4 is Monday 9.
    session.add_block(fixed("club", "Club", 5, "16:00"))
    session.save()
    wait_until(qapp, lambda: not session.busy and session.pending_save is None)
    assert session.save_routine("Clubs", ["club"])
    wait_until(qapp, lambda: not session.busy and bool(session.routines))
    (routine,) = session.routines.values()
    assert [template["days"] for template in routine["blocks"]] == [[0]]
    # Copied into the week from Wednesday 11, Monday 16 is its day 5; into Monday 16's week, day 0.
    rows = session.apply_routine_rows(routine["id"], "2026-11-11", [5])
    assert [(row["week_start"], row["day"]) for row in rows or []] == [("2026-11-11", 5)]
    rows = session.apply_routine_rows(routine["id"], "2026-11-16", [0])
    assert [(row["week_start"], row["day"]) for row in rows or []] == [("2026-11-16", 0)]


def test_plan_does_not_take_this_weeks_own_days_for_an_earlier_week(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in_from(qapp, server.origin, "earlier", WEDNESDAY)
    session.add_homework(essay(session, 60))
    # Wednesday 4 at 8:00 AM, day 0 of the week on screen and already over, is stored in Monday 2's
    # week, which starts before it. Plan keeps a missed session of this week where it is; only one
    # from an earlier week moves.
    for block in session.blocks:
        if block.get("assignment_id") == "essay":
            block["days"], block["start"] = [0], "08:00"
    session.save()
    wait_until(qapp, lambda: not session.busy and session.pending_save is None)
    session.add_homework({**essay(session, 30), "id": "quiz", "title": "Quiz"})
    session.solve()
    wait_until(qapp, lambda: not session.busy and not session.planning and session.pending_save is None)
    settled(qapp, session)
    assert essay_sessions(session.blocks) == [(0, "08:00", 60)]
    stored = essay_sessions(read_week(qapp, session, "2026-11-02")["blocks"])
    assert stored == [(2, "08:00", 60)]


def post_changes(qapp: QApplication, session: NativeSession, body: dict) -> None:
    """A change made somewhere else, such as on the phone, straight to the server."""
    got: dict = {}
    session.client.request(
        "POST",
        "/api/changes",
        body,
        lambda data: got.setdefault("ok", data),
        lambda error: got.setdefault("err", error),
    )
    wait_until(qapp, lambda: bool(got))
    assert "ok" in got, got.get("err")


def school_rows(blocks: list[dict]) -> list[tuple[str, list[int]]]:
    return sorted((block["start"], block["days"]) for block in blocks if block["title"] == "School")


def delete_choices(host: QWidget, monkeypatch: pytest.MonkeyPatch, block: dict) -> list[str]:
    """The answers the delete question offers for a block, left unanswered."""
    offered: list[str] = []

    class Asked:
        answer = "stay"

        def __init__(self, _parent, _title, _question, answers, **_kwargs) -> None:  # type: ignore[no-untyped-def]
            offered.extend(label for _key, label, _style in answers)

        def exec(self) -> int:
            return 0

    monkeypatch.setattr(widgets, "ConfirmSheet", Asked)
    monkeypatch.setattr(widgets, "confirm", lambda *_args: offered.append("Delete") and False)
    BlockDialog(host, block)._delete()
    return offered


def test_school_changed_twice_from_a_wednesday_week_on_and_then_from_monday_stays_school(
    qapp: QApplication, server: LocalServer, host: QWidget, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = signed_in_from(qapp, server.origin, "schooltwice", WEDNESDAY)
    school = {"id": SETUP_SCHOOL_ID, "title": "School", "kind": "locked", "category": "class",
              "start": "08:30", "duration_min": 390, "days": [0, 1, 2, 3, 4]}  # fmt: skip
    fields = {key: school[key] for key in ("title", "category", "start", "duration_min")}
    stands = {"id": SETUP_SCHOOL_ID, "scope": "from", "from_date": "2026-10-26", "add_days": [0, 1, 2, 3, 4],
              "set": fields}  # fmt: skip
    post_changes(qapp, session, {"weeks": [], "repeats": [stands]})
    session.reload()
    settled(qapp, session)
    for start in ("10:00", "09:00"):
        # School hours, from this week on.
        session.change_repeats([{**session.repeats[0], "start": start}], "changing School hours")
        session.save()
        wait_until(qapp, lambda: not session.busy and session.pending_save is None)
        settled(qapp, session)
        assert [(row["id"], row["start"], row["days"]) for row in session.blocks] == [
            (SETUP_SCHOOL_ID, start, [0, 1, 2, 5, 6])
        ]
    # Monday 2 and Tuesday 3 November come before the week on screen and keep 08:30.
    before = read_week(qapp, session, "2026-11-02")["blocks"]
    assert school_rows(before) == [("08:30", [0, 1]), ("09:00", [2, 3, 4])]
    nine = read_week(qapp, session, "2026-11-09")["blocks"]
    assert [(block["id"], block["start"], block["days"]) for block in nine] == [
        (SETUP_SCHOOL_ID, "09:00", [0, 1, 2, 3, 4])
    ]
    # Setup changed from Monday 9 November on, on another device: Monday 9 and Tuesday 10 follow it.
    setup = {"id": SETUP_SCHOOL_ID, "scope": "from", "from_date": "2026-11-09", "set": {"start": "07:45"}}
    post_changes(qapp, session, {"weeks": [], "repeats": [setup]})
    session.reload()
    settled(qapp, session)
    assert school_rows(read_week(qapp, session, "2026-11-09")["blocks"]) == [("07:45", [0, 1, 2, 3, 4])]
    assert school_rows(session.blocks) == [("07:45", [5, 6]), ("09:00", [0, 1, 2])]
    # Each School row on screen is School: deleting it asks this week only or this week and later.
    for row in session.blocks:
        assert delete_choices(host, monkeypatch, row) == ["Cancel", "This week only", "This week and later"]
    # This week and later, from either row, takes School off the whole week on screen and every week after.
    piece = next(row for row in session.blocks if row["id"] != SETUP_SCHOOL_ID)
    session.delete_block(piece["id"], every_week=True)
    session.save()
    wait_until(qapp, lambda: not session.busy and session.pending_save is None)
    settled(qapp, session)
    assert school_rows(session.blocks) == []
    assert school_rows(read_week(qapp, session, "2026-11-02")["blocks"]) == [("08:30", [0, 1])]
    assert school_rows(read_week(qapp, session, "2026-11-09")["blocks"]) == []
    assert school_rows(read_week(qapp, session, "2026-11-16")["blocks"]) == []


def test_a_waiting_session_deleted_and_undone_keeps_the_days_the_screen_cannot_see(
    qapp: QApplication, server: LocalServer
) -> None:
    # From Friday the week holding Thursday 5 November runs Friday 30 October to Thursday 5 November. A
    # session waiting for a time may go on Thursday 29 or Friday 30 October: the screen holds Friday.
    session = signed_in_from(qapp, server.origin, "waitingundo", 4)
    waiting = {"id": "hw", "title": "Read", "kind": "flexible", "duration_min": 60, "days": [3, 4]}
    post_changes(qapp, session, {"weeks": [{"week_start": "2026-10-26", "blocks": [waiting], "revision": 0}]})
    session.reload()
    settled(qapp, session)
    assert session.week_start == "2026-10-30"
    assert days_by_id({"blocks": session.blocks}) == {"hw": [0]}
    session.delete_block("hw")
    session.save()
    wait_until(qapp, lambda: not session.busy and session.pending_save is None)
    assert read_week(qapp, session, "2026-10-26")["blocks"] == []
    session.undo()
    wait_until(qapp, lambda: not session.busy and session.pending_save is None)
    settled(qapp, session)
    assert days_by_id(read_week(qapp, session, "2026-10-26")) == {"hw": [3, 4]}
    assert days_by_id({"blocks": session.blocks}) == {"hw": [0]}
    session.redo()
    wait_until(qapp, lambda: not session.busy and session.pending_save is None)
    settled(qapp, session)
    assert read_week(qapp, session, "2026-10-26")["blocks"] == []
    session.undo()
    wait_until(qapp, lambda: not session.busy and session.pending_save is None)
    settled(qapp, session)
    assert days_by_id(read_week(qapp, session, "2026-10-26")) == {"hw": [3, 4]}


def test_undoing_new_homework_planned_after_the_seam_takes_it_out_of_both_stored_weeks(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in_from(qapp, server.origin, "undohomework", WEDNESDAY)
    away = {"id": "busy", "title": "Away", "kind": "locked", "start": "00:00", "duration_min": 1440}
    session.add_block({**away, "days": [1, 2, 3, 4]})
    session.save()
    wait_until(qapp, lambda: not session.busy and session.pending_save is None)
    session.add_homework(essay(session, 120))
    session.save()
    wait_until(qapp, lambda: not session.busy and session.pending_save is None)
    session.solve()
    wait_until(qapp, lambda: not session.busy and not session.planning and session.pending_save is None)
    settled(qapp, session)
    # Planned on Monday 9 and Tuesday 10, after the seam.
    assert {day for day, *_ in essay_sessions(session.blocks)} <= {5, 6}
    assert essay_sessions(read_week(qapp, session, "2026-11-09")["blocks"]) != []
    for _ in range(2):
        session.undo()
        wait_until(qapp, lambda: not session.busy and session.pending_save is None)
        settled(qapp, session)
        assert not session.conflict, session.message
    assert "essay" not in session.assignments
    assert essay_sessions(session.blocks) == []
    for stored in ("2026-11-02", "2026-11-09"):
        assert not any(block.get("assignment_id") for block in read_week(qapp, session, stored)["blocks"])
    assert days_by_id(read_week(qapp, session, "2026-11-02")) == {"busy": [3, 4, 5, 6]}


def test_three_changes_in_a_wednesday_week_undo_one_by_one_without_a_conflict(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in_from(qapp, server.origin, "undothree", WEDNESDAY)

    def saved() -> None:
        session.save()
        wait_until(qapp, lambda: not session.busy and session.pending_save is None)
        settled(qapp, session)

    def stored(week_start: str) -> dict[str, list[int]]:
        return days_by_id(read_week(qapp, session, week_start))

    # Thursday 5 and Friday 6 are in Monday 2's stored week; Monday 9 starts the next.
    session.add_block(fixed("thu5", "Club", 1, "16:00"))
    saved()
    session.add_block(fixed("fri6", "Swim", 2, "07:00"))
    saved()
    session.add_homework(essay(session, 60))
    on_monday = {"id": "essay-1", "title": "Essay", "kind": "flexible", "assignment_id": "essay",
                 "start": "16:00", "duration_min": 60, "days": [5]}  # fmt: skip
    session.add_block(on_monday)
    # A change of its own in the same stored week: Undo then has to name that week's revision after the
    # homework's sessions are taken out of it.
    session.add_block(fixed("mon9", "Gym", 5, "18:00"))
    saved()
    assert stored("2026-11-09") == {"essay-1": [0], "mon9": [0]}
    for left in ({"thu5": [3], "fri6": [4]}, {"thu5": [3]}, {}):
        session.undo()
        wait_until(qapp, lambda: not session.busy and session.pending_save is None)
        settled(qapp, session)
        assert not session.conflict, session.message
        assert stored("2026-11-02") == left
        assert stored("2026-11-09") == {}
    assert "essay" not in session.assignments
