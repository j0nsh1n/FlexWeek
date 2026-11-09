"""A week to plan in, and the helpers the planning tests share. The `window` fixture here opens the week
as it is on Thursday at 10:00; test_homework_plan.py re-exports these names for the tests that still
import them from there."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime, time, timedelta
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from backend.tests.fake_clock import CLOCK, START_MONDAY
from desktop.native.calendar import date_for_day, sunday_due
from desktop.native.widgets import ConfirmSheet, HomeworkDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import LightWindows
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

TOO_LATE = "That due time has passed. Choose a later one."
PAST_WEEK = "This week is over, so nothing was planned. Plan this week or a later one."
THURSDAY_AT_TEN = datetime.combine(START_MONDAY + timedelta(days=3), time(10, 0))


def settled(qapp: QApplication, window: NativeWindow) -> None:  # noqa: F811
    """Every save made and every reply handled."""
    session = window.session
    wait_until(
        qapp,
        lambda: not session.busy and not session.dirty and not getattr(session.client, "pending", 0),
        what="the session settled",
    )


@pytest.fixture()
def window(
    qapp: QApplication,  # noqa: F811
    tmp_path_factory: pytest.TempPathFactory,
    tmp_path: Path,
) -> Iterator[NativeWindow]:
    """This week: School Monday to Friday 08:00-14:30, the History essay placed by hand on Thursday
    19:00-20:00, and a Math worksheet due Sunday that still needs a time. The clock is Thursday 10:00."""
    CLOCK.set(THURSDAY_AT_TEN)
    windows = LightWindows(qapp, tmp_path_factory.getbasetemp(), tmp_path)
    try:
        made = windows.open()
        session = made.session
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
        settled(qapp, made)
        session.hand_move(session_of(made, "essay")["id"], -1, 3, 19 * 60, 20 * 60)
        session.save()
        settled(qapp, made)
        yield made
    finally:
        windows.close()


def session_of(window: NativeWindow, assignment_id: str) -> dict:
    return next(block for block in window.session.blocks if block.get("assignment_id") == assignment_id)


def thursday_iso(window: NativeWindow) -> str:
    return date_for_day(window.session.week_start, 3)


def stored_blocks(window: NativeWindow) -> list[dict]:
    return sorted(window.session.blocks, key=lambda block: block["id"])


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


def _plan_them_if_asked() -> None:
    """Solve asks 'Before planning' when homework was left over; answer it with Plan into this week."""
    sheet = QApplication.activeModalWidget()
    if isinstance(sheet, ConfirmSheet) and sheet.findChild(QLabel, "sheetTitle").text() == "Before planning":
        sheet.buttons["plan"].click()


def press_solve(window: NativeWindow) -> None:
    QTimer.singleShot(0, _plan_them_if_asked)
    window.findChild(QPushButton, "solveButton").click()


def held_solves(window: NativeWindow) -> tuple[list[dict], list[Callable[[], None]]]:
    """Every /api/solve the window sends is kept, unanswered, until a test releases it."""
    sent: list[dict] = []
    waiting: list[Callable[[], None]] = []
    real = window.session.client.request

    def request(verb, target, payload, on_success, on_error):
        if verb == "POST" and target == "/api/solve":
            sent.append(payload)
            waiting.append(lambda: real(verb, target, payload, on_success, on_error))
            return None
        return real(verb, target, payload, on_success, on_error)

    window.session.client.request = request  # type: ignore[method-assign]
    return sent, waiting
