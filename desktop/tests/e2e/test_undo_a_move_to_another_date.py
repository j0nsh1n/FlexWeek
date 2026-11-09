"""Undoing a move between weeks, against the real local server. Saved weeks are read back from it."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.calendar import date_for_day
from desktop.native.controller import NativeSession
from desktop.server import LocalServer
from desktop.tests import logic_support
from desktop.tests.e2e.saved_weeks import read_week
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


def test_undo_puts_both_weeks_back(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    first = session.week_start
    second = week_after(first)
    session.add_block(fixed("soccer", "Soccer", 0, "16:00"))
    session.save()
    settled(qapp, session)
    monday = date_for_day(first, 0)
    next_monday = date_for_day(second, 0)
    assert session.move_to_date("soccer", monday, next_monday) is True
    settled(qapp, session)
    session.undo()
    settled(qapp, session)
    source = read_week(qapp, session, first)
    dest = read_week(qapp, session, second)
    assert titles(source["blocks"]) == ["Soccer"]
    assert titles(dest["blocks"]) == []
    assert titles(session.blocks) == ["Soccer"]
    soccer = next(block for block in source["blocks"] if block["id"] == "soccer")
    assert soccer["days"] == [0]
    assert soccer["start"] == "16:00"


def test_undo_of_a_move_is_refused_when_the_other_week_changed_elsewhere(
    qapp: QApplication, server: LocalServer
) -> None:
    """A later save to the other week, not on this undo stack, is kept. Undo is a 409, the week is
    reloaded as it is saved, and both weeks stay as they are."""
    alice = signed_in(qapp, server.origin, "alice", create=True)
    first = alice.week_start
    second = week_after(first)
    alice.add_block(fixed("soccer", "Soccer", 0, "16:00"))
    alice.save()
    settled(qapp, alice)
    monday = date_for_day(first, 0)
    next_monday = date_for_day(second, 0)
    assert alice.move_to_date("soccer", monday, next_monday) is True
    settled(qapp, alice)
    bob = NativeSession(server.origin, qapp)
    logic_support.HELD.append(bob)
    bob.login("alice", PASSWORD)
    wait_until(qapp, lambda: bob.account is not None and not bob.busy)
    settled(qapp, bob)
    bob.load_week(second)
    settled(qapp, bob)
    bob.add_block(fixed("piano", "Piano", 0, "17:00"))
    bob.save()
    settled(qapp, bob)
    alice.undo()
    settled(qapp, alice)
    assert alice.conflict is False
    assert alice.message == "Undo did not go through. Your week was reloaded as it's saved."
    source = read_week(qapp, alice, first)
    dest = read_week(qapp, alice, second)
    assert titles(source["blocks"]) == []
    assert sorted(titles(dest["blocks"])) == ["Piano", "Soccer"]
