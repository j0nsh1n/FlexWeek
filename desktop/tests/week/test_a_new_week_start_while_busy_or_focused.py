"""Picking a new first day of the week while the window is busy, or while a focus timer runs. The clock
is Thursday 5 November 2026: from Monday the open week runs Monday 2 to Sunday 8 November, from
Wednesday it runs Wednesday 4 to Tuesday 10, where Thursday 5 is day 1."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import CLOCK
from desktop.native import fields
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.logic_support import essay, settled
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_a_week_start_picked_while_a_week_loads_opens_its_week_when_the_load_lands(
    qapp: QApplication, window: NativeWindow
) -> None:
    session = window.session
    assert session.week_start == "2026-11-02"
    session.load_week(session.week_start, discard=True)
    assert session.busy
    fields.save_week_starts_on("wednesday")
    wait_until(
        qapp,
        lambda: session.week_start == "2026-11-04" and not session.busy,
        timeout=5,
        what=lambda: f"open week {session.week_start}, busy {session.busy}",
    )


def test_homework_focused_before_the_week_start_changed_can_still_be_finished(
    qapp: QApplication, window: NativeWindow
) -> None:
    session = window.session
    session.add_homework(essay(session))
    # Its session on Thursday 5 November at 16:00, day 3 of the Monday week.
    session.blocks[0]["start"] = "16:00"
    session.blocks[0]["days"] = [3]
    session.save()
    settled(qapp, session)
    block_id = session.blocks[0]["id"]
    assert session.start_focus(block_id, 3) is True
    CLOCK.move(minutes=30)
    session.tick_focus()
    settled(qapp, session)
    assert session.focus["phase"] == "ended"
    fields.save_week_starts_on("wednesday")
    wait_until(qapp, lambda: session.week_start == "2026-11-04" and not session.busy)
    settled(qapp, session)
    assert session.finish_focused_homework() is True
    settled(qapp, session)
    assert session.assignments["essay"]["completed"] is True
    block = next(item for item in session.blocks if item["id"] == block_id)
    assert (block["completed"], block["completed_day"], block["start"]) == (True, 1, "16:00")
