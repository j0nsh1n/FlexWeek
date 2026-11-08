"""Focus minutes are credited to the homework and kept, and Finished after a focus session finishes the
homework where its session was."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import CLOCK
from desktop.native.controller import NativeSession
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.logic_support import essay, fail_once, place_on_monday, settled
from desktop.tests.window_support import qapp  # noqa: F401


def start_focus_on_first_block(session: NativeSession) -> None:
    assert session.start_focus(session.blocks[0]["id"], 0) is True


def tick_focus_after_half_an_hour(qapp: QApplication, session: NativeSession) -> None:
    CLOCK.move(minutes=30)
    session.tick_focus()
    settled(qapp, session)


def test_a_focus_credit_is_not_lost_behind_a_failed_save(qapp: QApplication, window: NativeWindow) -> None:
    session = window.session
    session.add_homework(essay(session))
    place_on_monday(qapp, session)
    session.add_homework({**session.assignments["essay"], "notes": "Cite two sources"})
    fail_once(session, "POST", "/api/changes")
    session.save()
    settled(qapp, session)
    start_focus_on_first_block(session)
    tick_focus_after_half_an_hour(qapp, session)
    assert session.conflict is False
    session.reload()
    settled(qapp, session)
    item = session.assignments["essay"]
    assert item["focus_minutes"] == 30
    assert item["notes"] == "Cite two sources"


def test_finished_after_a_focus_session_finishes_the_homework_where_it_was(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Finished used to write a finished day onto a session not yet marked finished, which the
    homework's own check turned away, so nothing was finished and nothing was said."""
    session = window.session
    session.add_homework(essay(session))
    place_on_monday(qapp, session)
    start_focus_on_first_block(session)
    tick_focus_after_half_an_hour(qapp, session)
    assert session.focus["phase"] == "ended"
    assert session.finish_focused_homework() is True
    settled(qapp, session)
    session.reload()
    settled(qapp, session)
    assert session.assignments["essay"]["completed"] is True
    block = session.blocks[0]
    assert (block["completed"], block["completed_day"], block["start"]) == (True, 0, "16:00")
