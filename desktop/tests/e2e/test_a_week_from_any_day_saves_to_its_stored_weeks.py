"""A week on screen that starts on Wednesday (or Sunday) holds the seven days from that day, and what
the student saves lands in the stored (Monday) week of each day. The shared clock is Thursday
5 November 2026: from Wednesday that week runs Wednesday 4 to Tuesday 10 November, which covers the
stored weeks of Monday 2 and Monday 9 November; from Sunday it runs Sunday 1 to Saturday 7 November."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.client import ApiError
from desktop.native.controller import NativeSession
from desktop.server import LocalServer
from desktop.tests.e2e.account_sessions import HASHING_WAIT, HELD, server  # noqa: F401
from desktop.tests.e2e.saved_weeks import read_week
from desktop.tests.logic_support import fixed, settled
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import PASSWORD, qapp  # noqa: F401

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
