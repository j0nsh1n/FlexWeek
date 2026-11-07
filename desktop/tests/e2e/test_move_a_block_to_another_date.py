"""Moving a block to another date, against the real local server. Saved weeks are read back from it."""

from __future__ import annotations

from copy import deepcopy

from PySide6.QtWidgets import QApplication

from desktop.native.calendar import date_for_day, sunday_due
from desktop.native.controller import NativeSession
from desktop.server import LocalServer
from desktop.tests import logic_support
from desktop.tests.blocks_helper import put_block
from desktop.tests.e2e.saved_weeks import hold_the_clock_at_the_start_of_the_open_week, read_week
from desktop.tests.logic_support import (  # noqa: F401
    PASSWORD,
    fixed,
    qapp,
    server,
    settled,
    signed_in,
    titles,
    week_after,
)
from desktop.tests.waiting import wait_until

# The fixtures are used by name, so each test's argument list redefines them.
# ruff: noqa: F811

PAST_DUE = "That ends after it's due, so it stayed where it was."


def test_a_block_moved_to_another_day_of_the_week_keeps_its_time(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    hold_the_clock_at_the_start_of_the_open_week(session)
    session.add_block(fixed("soccer", "Soccer", 0, "16:00"))
    session.save()
    settled(qapp, session)
    monday = date_for_day(session.week_start, 0)
    wednesday = date_for_day(session.week_start, 2)
    assert session.move_to_date("soccer", monday, wednesday) is True
    settled(qapp, session)
    stored = read_week(qapp, session, session.week_start)
    soccer = next(block for block in stored["blocks"] if block["id"] == "soccer")
    assert soccer["days"] == [2]
    assert soccer["start"] == "16:00"
    assert soccer["duration_min"] == 60


def test_a_block_moved_to_next_week_is_written_to_both_weeks(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    first = session.week_start
    second = week_after(first)
    session.add_block({**fixed("soccer", "Soccer", 3, "16:07"), "duration_min": 43})
    session.save()
    settled(qapp, session)
    thursday = date_for_day(first, 3)
    next_tuesday = date_for_day(second, 1)
    assert session.move_to_date("soccer", thursday, next_tuesday) is True
    settled(qapp, session)
    assert session.conflict is False
    source = read_week(qapp, session, first)
    dest = read_week(qapp, session, second)
    assert titles(source["blocks"]) == []
    soccer = dest["blocks"][0]
    assert soccer["id"] == "soccer"
    assert soccer["days"] == [1]
    assert (soccer["start"], soccer["duration_min"]) == ("16:07", 43), "carried with its time exactly"
    assert session.week_start == first
    assert titles(session.blocks) == []


def test_a_block_moved_to_an_earlier_week_is_written_to_both_weeks(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    hold_the_clock_at_the_start_of_the_open_week(session)
    first = session.week_start
    second = week_after(first)
    session.load_week(second)
    settled(qapp, session)
    session.add_block(fixed("soccer", "Soccer", 1, "16:00"))
    session.save()
    settled(qapp, session)
    tuesday = date_for_day(second, 1)
    previous_thursday = date_for_day(first, 3)
    assert session.move_to_date("soccer", tuesday, previous_thursday) is True
    settled(qapp, session)
    source = read_week(qapp, session, second)
    dest = read_week(qapp, session, first)
    assert titles(source["blocks"]) == []
    soccer = dest["blocks"][0]
    assert soccer["days"] == [3]
    assert soccer["start"] == "16:00"


def test_moving_one_day_of_a_repeating_block_leaves_its_other_days_where_they_were(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    first = session.week_start
    second = week_after(first)
    session.add_block(
        {
            "id": "soccer",
            "title": "Soccer",
            "kind": "locked",
            "duration_min": 60,
            "days": [0, 2, 4],
            "start": "16:00",
        }
    )
    session.save()
    settled(qapp, session)
    monday = date_for_day(first, 0)
    next_monday = date_for_day(second, 0)
    assert session.move_to_date("soccer", monday, next_monday) is True
    settled(qapp, session)
    source = read_week(qapp, session, first)
    dest = read_week(qapp, session, second)
    remaining = next(block for block in source["blocks"] if block["id"] == "soccer")
    assert remaining["days"] == [2, 4]
    assert remaining["start"] == "16:00"
    moved = dest["blocks"][0]
    assert moved["id"] != "soccer"
    assert moved["days"] == [0]
    assert moved["start"] == "16:00"
    assert moved["title"] == "Soccer"


def test_homework_is_not_moved_to_a_day_after_it_is_due(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    hold_the_clock_at_the_start_of_the_open_week(session)
    due = date_for_day(session.week_start, 3) + "T15:00"
    session.add_homework({"id": "essay", "title": "Essay", "due": due, "estimate_min": 60, "revision": 0})
    session.save()
    settled(qapp, session)
    waiting = session.blocks[0]
    assert session.hand_move(waiting["id"], -1, 2, 16 * 60, 17 * 60) is True
    session.save()
    settled(qapp, session)
    wednesday = date_for_day(session.week_start, 2)
    friday = date_for_day(session.week_start, 4)
    assert session.date_problem(waiting["id"], wednesday, friday) == PAST_DUE
    before = read_week(qapp, session, session.week_start)
    assert session.move_to_date(waiting["id"], wednesday, friday) is False
    settled(qapp, session)
    after = read_week(qapp, session, session.week_start)
    assert after["blocks"] == before["blocks"]
    assert session.message == PAST_DUE


def test_homework_the_student_pinned_stays_pinned_in_the_new_week(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    first = session.week_start
    second = week_after(first)
    session.add_homework(
        {
            "id": "essay",
            "title": "Essay",
            "due": sunday_due(second),
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.save()
    settled(qapp, session)
    waiting = session.blocks[0]
    put_block(session, waiting["id"], 0, 16 * 60, 17 * 60, pinned=True)
    session.save()
    settled(qapp, session)
    monday = date_for_day(first, 0)
    next_tuesday = date_for_day(second, 1)
    assert session.move_to_date(waiting["id"], monday, next_tuesday) is True
    settled(qapp, session)
    dest = read_week(qapp, session, second)
    essay = dest["blocks"][0]
    assert essay["assignment_id"] == "essay"
    assert essay["pinned"] is True
    assert essay["start"] == "16:00"


def test_a_move_refused_because_the_other_week_changed_leaves_both_weeks_untouched(
    qapp: QApplication, server: LocalServer
) -> None:
    alice = signed_in(qapp, server.origin, "alice", create=True)
    first = alice.week_start
    second = week_after(first)
    alice.add_block(fixed("soccer", "Soccer", 0, "16:00"))
    alice.save()
    settled(qapp, alice)
    bob = NativeSession(server.origin, qapp)
    logic_support.HELD.append(bob)
    bob.login("alice", PASSWORD)
    wait_until(qapp, lambda: bob.account is not None and not bob.busy)
    settled(qapp, bob)
    bob.load_week(second)
    settled(qapp, bob)
    real = alice.client.request

    def request(verb, target, payload, on_success, on_error):
        if verb == "GET" and f"week_start={second}" in target:
            alice.client.request = real  # type: ignore[method-assign]

            def hooked(data):
                bob.add_block(fixed("piano", "Piano", 0, "17:00"))
                bob.save()
                settled(qapp, bob)
                on_success(data)

            return real(verb, target, payload, hooked, on_error)
        return real(verb, target, payload, on_success, on_error)

    alice.client.request = request  # type: ignore[method-assign]
    monday = date_for_day(first, 0)
    next_monday = date_for_day(second, 0)
    assert alice.move_to_date("soccer", monday, next_monday) is True
    settled(qapp, alice)
    assert alice.conflict is True
    source = read_week(qapp, alice, first)
    dest = read_week(qapp, alice, second)
    assert titles(source["blocks"]) == ["Soccer"]
    assert titles(dest["blocks"]) == ["Piano"]
    assert titles(alice.blocks) == ["Soccer"]


def test_sending_the_same_move_again_moves_the_block_once(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    first = session.week_start
    second = week_after(first)
    session.add_block(fixed("soccer", "Soccer", 0, "16:00"))
    session.save()
    settled(qapp, session)
    captured: dict = {}
    real = session.client.request

    def request(verb, target, payload, on_success, on_error):
        if verb == "POST" and target.startswith("/api/changes"):
            captured["payload"] = deepcopy(payload)
        return real(verb, target, payload, on_success, on_error)

    session.client.request = request  # type: ignore[method-assign]
    monday = date_for_day(first, 0)
    next_monday = date_for_day(second, 0)
    assert session.move_to_date("soccer", monday, next_monday) is True
    settled(qapp, session)
    replayed: dict = {}

    def ok(data: dict) -> None:
        replayed["ok"] = data

    def err(error) -> None:
        replayed["err"] = error

    session.client.request("POST", "/api/changes", captured["payload"], ok, err)
    settled(qapp, session)
    assert "ok" in replayed
    dest = read_week(qapp, session, second)
    source = read_week(qapp, session, first)
    assert titles(source["blocks"]) == []
    assert titles(dest["blocks"]) == ["Soccer"]
    assert [block["id"] for block in dest["blocks"]] == ["soccer"]


def test_the_open_week_does_not_change_until_the_server_accepts_the_move(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    first = session.week_start
    second = week_after(first)
    session.add_block(fixed("soccer", "Soccer", 0, "16:00"))
    session.save()
    settled(qapp, session)
    seen: dict = {}
    real = session.client.request

    def request(verb, target, payload, on_success, on_error):
        if verb == "POST" and target.startswith("/api/changes"):
            seen["titles"] = titles(session.blocks)
            seen["days"] = next(block["days"] for block in session.blocks if block["id"] == "soccer")
        return real(verb, target, payload, on_success, on_error)

    session.client.request = request  # type: ignore[method-assign]
    monday = date_for_day(first, 0)
    next_monday = date_for_day(second, 0)
    assert session.move_to_date("soccer", monday, next_monday) is True
    settled(qapp, session)
    assert seen["titles"] == ["Soccer"]
    assert seen["days"] == [0]
    assert titles(session.blocks) == []
    dest = read_week(qapp, session, second)
    assert titles(dest["blocks"]) == ["Soccer"]


def test_a_move_into_a_week_that_already_has_blocks_keeps_them(
    qapp: QApplication, server: LocalServer
) -> None:
    """The other week is rewritten whole, so what it already held must come along: a plain block
    and one day of a repeating block both arrive beside what was there."""
    session = signed_in(qapp, server.origin, "alice", create=True)
    first = session.week_start
    second = week_after(first)
    session.load_week(second)
    settled(qapp, session)
    session.add_block(fixed("piano", "Piano", 2, "18:00"))
    session.save()
    settled(qapp, session)
    session.load_week(first)
    settled(qapp, session)
    session.add_block(fixed("soccer", "Soccer", 3, "16:00"))
    session.add_block(
        {
            "id": "band",
            "title": "Band",
            "kind": "locked",
            "duration_min": 60,
            "days": [0, 2, 4],
            "start": "17:00",
        }
    )
    session.save()
    settled(qapp, session)
    assert session.move_to_date("soccer", date_for_day(first, 3), date_for_day(second, 1)) is True
    settled(qapp, session)
    assert session.move_to_date("band", date_for_day(first, 0), date_for_day(second, 0)) is True
    settled(qapp, session)
    dest = read_week(qapp, session, second)
    assert sorted(titles(dest["blocks"])) == ["Band", "Piano", "Soccer"]
    assert next(block for block in dest["blocks"] if block["title"] == "Piano")["days"] == [2]
    source = read_week(qapp, session, first)
    assert sorted(titles(source["blocks"])) == ["Band"]
    assert next(block for block in source["blocks"] if block["title"] == "Band")["days"] == [2, 4]


def test_a_chip_in_a_week_that_is_not_open_is_judged_against_its_due_time(
    qapp: QApplication, server: LocalServer
) -> None:
    """Month has the chip's start and length from the month reply, not from the open week."""
    session = signed_in(qapp, server.origin, "alice", create=True)
    hold_the_clock_at_the_start_of_the_open_week(session)
    first = session.week_start
    second = week_after(first)
    due = date_for_day(first, 3) + "T15:00"
    session.add_homework({"id": "essay", "title": "Essay", "due": due, "estimate_min": 60, "revision": 0})
    session.save()
    settled(qapp, session)
    waiting = session.blocks[0]
    assert session.hand_move(waiting["id"], -1, 2, 16 * 60, 17 * 60) is True
    session.save()
    settled(qapp, session)
    chip = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    wednesday = date_for_day(first, 2)
    friday = date_for_day(first, 4)
    tuesday = date_for_day(first, 1)
    session.load_week(second)
    settled(qapp, session)
    assert session.week_start == second
    assert all(block.get("id") != chip["id"] for block in session.blocks)
    assert (
        session.date_problem(
            chip["id"],
            wednesday,
            friday,
            start=chip["start"],
            duration_min=chip["duration_min"],
            assignment_id=chip["assignment_id"],
        )
        == PAST_DUE
    )
    assert (
        session.date_problem(
            chip["id"],
            wednesday,
            tuesday,
            start=chip["start"],
            duration_min=chip["duration_min"],
            assignment_id=chip["assignment_id"],
        )
        is None
    )
