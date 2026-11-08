"""What the server keeps: each Monday is its own week, two accounts never see each other's week, a reply
that arrives after the client was reset is ignored, and a save made from an old copy keeps the draft."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.server import LocalServer
from desktop.tests.e2e.account_sessions import server, signed_in, soccer  # noqa: F401
from desktop.tests.logic_support import fixed, titles, week_after
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_a_different_monday_loads_as_its_own_empty_week(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    start = session.week_start
    session.add_block(soccer())
    session.save()
    wait_until(qapp, lambda: session.revision == 1 and not session.busy)
    nxt = week_after(start)
    session.load_week(nxt)
    wait_until(qapp, lambda: session.week_start == nxt and not session.busy)
    assert session.blocks == []
    assert session.revision == 0
    session.load_week(start)
    wait_until(qapp, lambda: session.week_start == start and not session.busy)
    assert titles(session.blocks) == ["Soccer"]


def test_two_accounts_do_not_see_each_others_week(qapp: QApplication, server: LocalServer) -> None:
    alice = signed_in(qapp, server.origin, "alice", create=True)
    alice.add_block(soccer())
    alice.save()
    wait_until(qapp, lambda: alice.revision == 1 and not alice.busy)
    bob = signed_in(qapp, server.origin, "bob", create=True)
    assert bob.blocks == []
    assert bob.revision == 0
    assert set(titles(alice.blocks)) == {"Soccer"}


def test_a_reply_that_arrives_after_a_reset_is_not_applied(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    heard: list[object] = []
    session.client.request(
        "GET",
        f"/api/week?week_start={session.week_start}",
        None,
        heard.append,
        heard.append,
    )
    before = session.client.epoch
    session.client.reset()
    assert session.client.epoch == before + 1
    # The request on its way was cancelled with the reset: wait until the client holds none, then see
    # that neither of its callbacks was called.
    wait_until(qapp, lambda: not any(session.client._replies.values()))
    assert heard == []


def test_a_week_saved_from_an_old_copy_keeps_the_draft(qapp: QApplication, server: LocalServer) -> None:
    alice = signed_in(qapp, server.origin, "alice", create=True)
    other = signed_in(qapp, server.origin, "alice", create=False)
    alice.add_block(soccer())
    alice.save()
    wait_until(qapp, lambda: alice.revision == 1 and not alice.busy)
    other.add_block(fixed("piano", "Piano", 1, "17:00"))
    other.save()
    wait_until(qapp, lambda: other.conflict or (other.revision == 1 and not other.busy))
    assert other.conflict
    assert other.pending_save is not None
    assert titles(other.blocks) == ["Piano"]
    assert other.message.startswith("Not saved.")
