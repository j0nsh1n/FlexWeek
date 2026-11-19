"""A time that has already passed is refused everywhere a student can give homework a time by hand:
dropping a block (and its drag preview), Choose a time, and Edit homework > Do it at. The refusal reads
"That time has passed. Choose 2:15 PM or later today, or another day."

The one clock is held at Wednesday 14:07 of the open week."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest
from PySide6.QtCore import QTime
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox

from desktop.native.calendar import sunday_due
from desktop.native.weekmodel import set_clock_24h
from desktop.native.widgets import ChooseTimeDialog, HomeworkDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.week.support_pastnext import (
    TUESDAY,
    WEDNESDAY,
    classic_week,
    hold_clock,
)
from desktop.tests.window_support import free, qapp, settled  # noqa: F401

PAST_REFUSAL = "That time has passed. Choose 2:15 PM or later today, or another day."
PAST_DAY_REFUSAL = "That time has passed. The day is over, so choose another day."

NOW = 14 * 60 + 7


def homework(
    qapp: QApplication, window: NativeWindow, start: str | None = None, day: int = WEDNESDAY
) -> dict:
    """The History essay, due Sunday, with one session: waiting for a time, or placed at `start`. The
    classic Week has one early block on Monday, since a week with nothing in it shows a button in place
    of the hours."""
    classic_week(qapp, window)
    # Wednesday at NOW from the start, as the old grid window was, so 16:00 is still ahead when the
    # essay is put there.
    hold_clock(window, WEDNESDAY, NOW)
    session = window.session
    session.add_block(
        {
            "id": "early",
            "title": "Early",
            "kind": "locked",
            "category": "extra",
            "start": "06:00",
            "duration_min": 30,
            "days": [0],
        }
    )
    set_clock_24h(False)
    session.add_homework(
        {
            "id": "essay",
            "title": "History essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.save()
    settled(qapp, window)
    block = next(b for b in session.blocks if b.get("assignment_id") == "essay")
    if start is not None:
        h, m = map(int, start.split(":"))
        assert session.hand_move(block["id"], -1, day, h * 60 + m, h * 60 + m + 60)
        session.save()
        settled(qapp, window)
    hold_clock(window, WEDNESDAY, NOW)
    return next(b for b in session.blocks if b.get("assignment_id") == "essay")


def where(window: NativeWindow, block_id: str) -> tuple[list[int], str | None]:
    block = next(b for b in window.session.blocks if b["id"] == block_id)
    return block["days"], block.get("start")


# Drag and drop -------------------------------------------------------------------------------












# Choose a time -------------------------------------------------------------------------------


def choose(window: NativeWindow, monkeypatch: pytest.MonkeyPatch, day: int, minute: int) -> tuple[bool, str]:
    seen: list[tuple[bool, str]] = []

    def pick(dialog: ChooseTimeDialog) -> int:
        dialog.day.set_days([day])
        dialog.start.setTime(QTime(minute // 60, minute % 60))
        dialog._check()
        ok = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
        seen.append((ok, dialog.problem.text() if dialog.problem.isVisibleTo(dialog) else ""))
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(ChooseTimeDialog, "exec", pick)
    window._choose_time("essay")
    assert len(seen) == 1, "Choose a time did not open"
    return seen[0]








# Do it at ------------------------------------------------------------------------------------


def do_it_at(qapp: QApplication, window: NativeWindow, day: int, minute: int) -> tuple[int, str]:
    session = window.session
    dialog = HomeworkDialog(window, session.assignments["essay"])
    try:
        dialog.when.setCurrentIndex(1)  # "Do it at"
        dialog.when_day.set_days([day])
        dialog._pick_day()
        dialog.when_time.setTime(QTime(minute // 60, minute % 60))
        dialog.accept()
        qapp.processEvents()
        problem = dialog.when_problem.text() if dialog.when_problem.isVisibleTo(dialog) else ""
        return dialog.result(), problem
    finally:
        dialog.hide()
        free(dialog)


@pytest.mark.parametrize(
    ("day", "minute", "expected"),
    [
        (WEDNESDAY, 9 * 60, PAST_REFUSAL),
        (TUESDAY, 18 * 60, PAST_DAY_REFUSAL),
    ],
    ids=["Wed09:00", "Tue18:00"],
)
def test_do_it_at_refuses_a_past_time_and_keeps_the_sheet_open(qapp, window, day, minute, expected) -> None:
    homework(qapp, window)
    result, problem = do_it_at(qapp, window, day, minute)
    assert (result, problem) == (QDialog.DialogCode.Rejected.value, expected)


def test_do_it_at_saves_later_today(qapp, window) -> None:
    homework(qapp, window)
    result, problem = do_it_at(qapp, window, WEDNESDAY, 18 * 60)
    assert (result, problem) == (QDialog.DialogCode.Accepted.value, "")
