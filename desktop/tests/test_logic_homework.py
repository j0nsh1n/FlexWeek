"""Homework edits against a real local API. Expected values follow frontend/day.js saveHomework."""

from __future__ import annotations

import importlib.util
from copy import deepcopy

import pytest

from desktop.tests import logic_support

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)
qapp = logic_support.qapp
server = logic_support.server

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtWidgets import QApplication

    from desktop.native.calendar import sunday_due
    from desktop.native.controller import NativeSession
    from desktop.native.reuse import copied_homework_block
    from desktop.server import LocalServer
    from desktop.tests.logic_support import settled, signed_in


def spread_essay(qapp: QApplication, session: NativeSession) -> list[tuple]:
    """One 90 minute essay held as three 30 minute sessions, the shape Spread and homework paste save."""
    session.add_homework(
        {
            "id": "essay",
            "title": "Essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 90,
            "revision": 0,
        }
    )
    session.save()
    settled(qapp, session)
    sessions = []
    for index, day in enumerate((0, 2, 4)):
        block = copied_homework_block(session.assignments["essay"], day, 30, f"essay-part-{index}")
        block["start"] = "16:00"
        sessions.append(block)
    session.blocks = sessions
    session._touch("spreading Essay")
    session.save()
    settled(qapp, session)
    return shape(session)


def shape(session: NativeSession) -> list[tuple]:
    return sorted(
        (block["id"], block["days"], block["start"], block["duration_min"])
        for block in session.blocks
        if block.get("assignment_id") == "essay"
    )


THREE_SESSIONS = [
    ("essay-part-0", [0], "16:00", 30),
    ("essay-part-1", [2], "16:00", 30),
    ("essay-part-2", [4], "16:00", 30),
]


def test_a_notes_edit_keeps_every_session_of_the_homework(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    assert spread_essay(qapp, session) == THREE_SESSIONS
    session.add_homework({**session.assignments["essay"], "notes": "Cite two sources"})
    assert shape(session) == THREE_SESSIONS
    session.save()
    settled(qapp, session)
    session.reload()
    settled(qapp, session)
    assert shape(session) == THREE_SESSIONS
    assert session.assignments["essay"]["notes"] == "Cite two sources"


def test_a_new_title_reaches_every_session(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    spread_essay(qapp, session)
    session.add_homework({**session.assignments["essay"], "title": "History essay"})
    titles = [block["title"] for block in session.blocks if block.get("assignment_id") == "essay"]
    assert titles == ["History essay", "History essay", "History essay"]
    assert shape(session) == THREE_SESSIONS


def test_completing_homework_keeps_its_sessions(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    spread_essay(qapp, session)
    session.complete_homework("essay")
    assert shape(session) == THREE_SESSIONS
    session.save()
    settled(qapp, session)
    assert session.conflict is False
    assert shape(session) == THREE_SESSIONS
    assert session.assignments["essay"]["completed"] is True


def test_a_single_whole_session_still_follows_a_new_estimate(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.add_homework(
        {
            "id": "essay",
            "title": "Essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.save()
    settled(qapp, session)
    session.add_homework({**session.assignments["essay"], "estimate_min": 90})
    assert [block["duration_min"] for block in session.blocks] == [90]


def test_a_partial_session_is_not_stretched_to_the_estimate(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.add_homework(
        {
            "id": "essay",
            "title": "Essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 120,
            "revision": 0,
        }
    )
    session.blocks[0]["duration_min"] = 60
    session.save()
    settled(qapp, session)
    session.add_homework({**session.assignments["essay"], "notes": "Half was done last week"})
    assert [block["duration_min"] for block in session.blocks] == [60]


def test_an_edit_from_an_older_copy_keeps_focus_credit_and_saves(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.add_homework(
        {
            "id": "essay",
            "title": "Essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.blocks[0]["start"] = "16:00"
    session.blocks[0]["days"] = [0]
    session.save()
    settled(qapp, session)
    session.now_ms = lambda: 1_000_000
    assert session.start_focus(session.blocks[0]["id"], 0) is True
    # The homework dialog deep-copies the assignment when it opens and stays open across the tick.
    opened = deepcopy(session.assignments["essay"])
    session.now_ms = lambda: 1_000_000 + 30 * 60_000
    session.tick_focus()
    settled(qapp, session)
    assert session.assignments["essay"]["focus_minutes"] == 30
    opened["checklist"] = [{"id": "step-1", "text": "Outline", "done": True}]
    session.add_homework(opened)
    session.save()
    settled(qapp, session)
    assert session.conflict is False
    session.reload()
    settled(qapp, session)
    item = session.assignments["essay"]
    assert item["focus_minutes"] == 30
    assert item["focus_sessions"] == 1
    assert item["checklist"] == [{"id": "step-1", "text": "Outline", "done": True}]
