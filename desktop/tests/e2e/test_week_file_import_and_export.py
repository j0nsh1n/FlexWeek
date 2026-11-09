"""A week file exported from one week or account and imported into another, through the real server."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import json
from datetime import date, timedelta

from PySide6.QtWidgets import QApplication

from desktop.server import LocalServer
from desktop.tests.e2e.account_sessions import HASHING_WAIT, server, signed_in, soccer  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_a_week_file_round_trip_replaces_the_open_week(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.add_block(soccer())
    session.save()
    wait_until(qapp, lambda: session.revision == 1 and not session.busy)
    payload = json.dumps(session.week_file())
    session.blocks = []
    session._touch("clearing")
    session.save()
    wait_until(qapp, lambda: session.blocks == [] and not session.busy)
    assert session.import_week_file(payload, replace=True) is True
    wait_until(qapp, lambda: not session.busy and any(block["id"] == "soccer" for block in session.blocks))


def test_replacing_the_week_from_a_file_waits_for_confirmation(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.add_block(soccer())
    session.save()
    wait_until(qapp, lambda: session.revision == 1 and not session.busy)
    payload = json.dumps(session.week_file())
    session.add_block({**soccer(), "id": "band", "title": "Band", "start": "18:00"})
    assert session.import_week_file(payload) is False
    assert any(block["id"] == "band" for block in session.blocks)
    assert session.import_week_file(payload, replace=True) is True
    wait_until(qapp, lambda: not session.busy)
    assert [block["id"] for block in session.blocks] == ["soccer"]


def test_importing_an_account_waits_for_unsaved_changes_to_be_saved(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.add_block(soccer())
    session.preview_account_import({"format": 3})
    assert session.transfer_preview is None
    assert session.message == "Save your last change first (More > Retry save), then import."


def test_reimporting_changed_homework_gets_its_own_homework(qapp: QApplication, server: LocalServer) -> None:
    """The second file's Essay has a new title and due date. Its sessions must not be attached to the
    homework the first import made, which keeps the old title and due date."""
    source = signed_in(qapp, server.origin, "alice", create=True)
    monday = date.fromisoformat(source.week_start)
    first_due = (monday + timedelta(days=3)).isoformat() + "T21:00"
    later_due = (monday + timedelta(days=4)).isoformat() + "T21:00"
    source.add_homework(
        {"id": "essay", "title": "Essay draft", "due": first_due, "estimate_min": 60, "revision": 0}
    )
    source.save()
    wait_until(qapp, lambda: not source.busy and not source.dirty and "essay" in source.assignments)
    first = json.dumps(source.week_file())
    source.add_homework({**source.assignments["essay"], "title": "Final essay", "due": later_due})
    source.save()
    wait_until(qapp, lambda: not source.busy and not source.dirty)
    second = json.dumps(source.week_file())
    source.logout()
    wait_until(qapp, lambda: source.account is None and not source.busy, HASHING_WAIT)

    target = signed_in(qapp, server.origin, "bob", create=True)

    def imported(raw: str) -> set[str]:
        assert target.import_week_file(raw, replace=True) is True
        wait_until(qapp, lambda: not target.busy and not target.dirty)
        target.reload()
        wait_until(qapp, lambda: not target.busy and bool(target.blocks))
        return {block["assignment_id"] for block in target.blocks if block.get("assignment_id")}

    [old_id] = imported(first)
    [new_id] = imported(second)
    assert new_id != old_id
    held = {key: (item["title"], item["due"]) for key, item in target.assignments.items()}
    assert held == {old_id: ("Essay draft", first_due), new_id: ("Final essay", later_due)}
    assert {block["title"] for block in target.blocks if block.get("assignment_id")} == {"Final essay"}
    # The same file again lands on the same homework and makes no third one.
    assert imported(second) == {new_id}
    assert len(target.assignments) == 2
