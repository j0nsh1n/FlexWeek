"""Editing homework keeps what hangs off it: every session of a spread homework survives a notes edit, a
new title reaches each session, finishing keeps the sessions, a single whole session follows a new
estimate but a part-done one does not, and an edit made from an older copy keeps the focus credit.
Expected values follow frontend/day.js saveHomework."""

from __future__ import annotations

from copy import deepcopy

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import CLOCK
from desktop.native.calendar import sunday_due
from desktop.native.reuse import copied_homework_block
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.sheets.support_homework_week import settled
from desktop.tests.window_support import qapp  # noqa: F401

THREE_SESSIONS = [
    ("essay-part-0", [0], "16:00", 30),
    ("essay-part-1", [2], "16:00", 30),
    ("essay-part-2", [4], "16:00", 30),
]


def essay_for(opened: NativeWindow, estimate_min: int = 60) -> dict:
    return {
        "id": "essay",
        "title": "Essay",
        "due": sunday_due(opened.session.week_start),
        "estimate_min": estimate_min,
        "revision": 0,
    }


def spread_essay(qapp: QApplication, opened: NativeWindow) -> list[tuple]:  # noqa: F811
    """One 90 minute essay held as three 30 minute sessions, the shape Spread and homework paste save."""
    session = opened.session
    session.add_homework(essay_for(opened, 90))
    session.save()
    settled(qapp, opened)
    sessions = []
    for index, day in enumerate((0, 2, 4)):
        block = copied_homework_block(session.assignments["essay"], day, 30, f"essay-part-{index}")
        block["start"] = "16:00"
        sessions.append(block)
    session.blocks = sessions
    session._touch("spreading Essay")
    session.save()
    settled(qapp, opened)
    return shape(opened)


def shape(opened: NativeWindow) -> list[tuple]:
    return sorted(
        (block["id"], block["days"], block["start"], block["duration_min"])
        for block in opened.session.blocks
        if block.get("assignment_id") == "essay"
    )


def test_a_notes_edit_keeps_every_session_of_the_homework(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    session = window.session
    assert spread_essay(qapp, window) == THREE_SESSIONS
    session.add_homework({**session.assignments["essay"], "notes": "Cite two sources"})
    assert shape(window) == THREE_SESSIONS
    session.save()
    settled(qapp, window)
    session.reload()
    settled(qapp, window)
    assert shape(window) == THREE_SESSIONS
    assert session.assignments["essay"]["notes"] == "Cite two sources"


def test_a_new_title_reaches_every_session(qapp: QApplication, window: NativeWindow) -> None:  # noqa: F811
    session = window.session
    spread_essay(qapp, window)
    session.add_homework({**session.assignments["essay"], "title": "History essay"})
    titles = [block["title"] for block in session.blocks if block.get("assignment_id") == "essay"]
    assert titles == ["History essay", "History essay", "History essay"]
    assert shape(window) == THREE_SESSIONS


def test_completing_homework_keeps_its_sessions(qapp: QApplication, window: NativeWindow) -> None:  # noqa: F811
    session = window.session
    spread_essay(qapp, window)
    session.complete_homework("essay")
    assert shape(window) == THREE_SESSIONS
    session.save()
    settled(qapp, window)
    assert session.conflict is False
    assert shape(window) == THREE_SESSIONS
    assert session.assignments["essay"]["completed"] is True


def test_a_single_whole_session_still_follows_a_new_estimate(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    session = window.session
    session.add_homework(essay_for(window))
    session.save()
    settled(qapp, window)
    session.add_homework({**session.assignments["essay"], "estimate_min": 90})
    assert [block["duration_min"] for block in session.blocks] == [90]


def test_a_partial_session_is_not_stretched_to_the_estimate(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    session = window.session
    session.add_homework(essay_for(window, 120))
    session.blocks[0]["duration_min"] = 60
    session.save()
    settled(qapp, window)
    session.add_homework({**session.assignments["essay"], "notes": "Half was done last week"})
    assert [block["duration_min"] for block in session.blocks] == [60]


def test_an_edit_from_an_older_copy_keeps_focus_credit_and_saves(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    session = window.session
    session.add_homework(essay_for(window))
    # Give the first block a Monday 16:00 start and save it.
    session.blocks[0]["start"] = "16:00"
    session.blocks[0]["days"] = [0]
    session.save()
    settled(qapp, window)
    assert session.start_focus(session.blocks[0]["id"], 0) is True
    # The homework dialog deep-copies the assignment when it opens and stays open across the tick.
    opened = deepcopy(session.assignments["essay"])
    CLOCK.move(minutes=30)
    session.tick_focus()
    settled(qapp, window)
    assert session.assignments["essay"]["focus_minutes"] == 30
    opened["checklist"] = [{"id": "step-1", "text": "Outline", "done": True}]
    session.add_homework(opened)
    session.save()
    settled(qapp, window)
    assert session.conflict is False
    session.reload()
    settled(qapp, window)
    item = session.assignments["essay"]
    assert item["focus_minutes"] == 30
    assert item["focus_sessions"] == 1
    assert item["checklist"] == [{"id": "step-1", "text": "Outline", "done": True}]
