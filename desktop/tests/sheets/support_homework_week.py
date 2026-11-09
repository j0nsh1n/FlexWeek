"""A light window with the week the homework tests share: School Monday to Friday 08:00-14:30, the
History essay placed by hand on Thursday 19:00-20:00, and a Math worksheet due Sunday that still needs
a time. The clock is held at Thursday 10:00 of that week."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

import pytest
from PySide6.QtWidgets import QApplication, QDialog

from backend.tests.fake_clock import CLOCK
from desktop.native.calendar import sunday_due
from desktop.native.widgets import HomeworkDialog
from desktop.native.window import NativeWindow
from desktop.tests.waiting import wait_until

THURSDAY_10_00 = datetime(2026, 11, 5, 10, 0)


def settled(qapp: QApplication, window: NativeWindow) -> None:
    """The foreground request and every reply still on its way have landed and nothing is unsaved."""
    wait_until(
        qapp,
        lambda: (
            not window.session.busy
            and not window.session.dirty
            and not getattr(window.session.client, "pending", 0)
        ),
        what="the window to finish saving",
    )


def session_of(window: NativeWindow, assignment_id: str) -> dict:
    return next(block for block in window.session.blocks if block.get("assignment_id") == assignment_id)


def sessions_of(window: NativeWindow, assignment_id: str) -> list[dict]:
    return sorted(
        (block for block in window.session.blocks if block.get("assignment_id") == assignment_id),
        key=lambda block: (block["days"][0], block.get("start") or ""),
    )


def opened_with(
    monkeypatch: pytest.MonkeyPatch, act: Callable[[HomeworkDialog], int]
) -> list[HomeworkDialog]:
    """Every homework editor the window opens is handed to `act` instead of waiting for a student."""
    seen: list[HomeworkDialog] = []

    def run(dialog: HomeworkDialog) -> int:
        seen.append(dialog)
        return act(dialog)

    monkeypatch.setattr(HomeworkDialog, "exec", run)
    return seen


def accepted(dialog: HomeworkDialog) -> int:
    dialog.accept()
    return QDialog.DialogCode.Accepted


def homework_week(qapp: QApplication, open_light: Callable[..., NativeWindow]) -> NativeWindow:
    CLOCK.set(THURSDAY_10_00)
    window = open_light()
    session = window.session
    session.selected_day = THURSDAY_10_00.date().isoformat()
    session.add_block(
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "category": "class",
            "start": "08:00",
            "duration_min": 390,
            "days": [0, 1, 2, 3, 4],
        }
    )
    due = sunday_due(session.week_start)
    for key, title in (("essay", "History essay"), ("math", "Math worksheet")):
        session.add_homework({"id": key, "title": title, "due": due, "estimate_min": 60, "revision": 0})
    session.save()
    settled(qapp, window)
    session.hand_move(session_of(window, "essay")["id"], -1, 3, 19 * 60, 20 * 60)
    session.save()
    settled(qapp, window)
    return window


@pytest.fixture()
def homework_window(qapp: QApplication, open_light: Callable[..., NativeWindow]) -> NativeWindow:
    return homework_week(qapp, open_light)
