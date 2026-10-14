"""Running late starts from the next quarter hour, rounded up (finding 5 of the 0.18.1 time lane): at
22:56 it said "Starting from 22:45", a time that had gone by."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialog, QLabel

from desktop.native.widgets import LateDialog
from desktop.native.window import NativeWindow
from desktop.tests.test_default_times import THURSDAY, hold_clock
from desktop.tests.test_drag_results import qapp, settled, wait_until, window  # noqa: F401


def running_late_says(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> tuple[str, list[tuple[int, int]]]:
    said: list[str] = []
    asked: list[tuple[int, int]] = []

    def look(dialog: LateDialog) -> int:
        said.extend(label.text() for label in dialog.findChildren(QLabel) if "Starting from" in label.text())
        dialog.preview_requested.emit()
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(LateDialog, "exec", look)
    monkeypatch.setattr(
        window.session,
        "preview_running_late",
        lambda minutes, now: asked.append((now.hour, now.minute)),
    )
    window._open_late()
    return said[0], asked


@pytest.mark.parametrize("twenty_four", [True, False])
@pytest.mark.parametrize(
    ("now", "start_24", "start_12", "from_start"),
    [
        ("22:56", "23:00", "11:00 PM", (23, 0)),
        ("22:46", "23:00", "11:00 PM", (23, 0)),
        ("22:45", "22:45", "10:45 PM", (22, 45)),
        ("22:45:30", "22:45", "10:45 PM", (22, 45)),
        ("22:01", "22:15", "10:15 PM", (22, 15)),
        ("23:50", "23:45", "11:45 PM", (23, 45)),
    ],
)
def test_running_late_starts_from_the_next_quarter_hour(
    qapp: QApplication,
    window: NativeWindow,
    monkeypatch: pytest.MonkeyPatch,
    now: str,
    start_24: str,
    start_12: str,
    from_start: tuple[int, int],
    twenty_four: bool,
) -> None:
    window.session.preferences = {**(window.session.preferences or {}), "clock_24h": twenty_four}
    window._sync_chrome()
    hold_clock(window, THURSDAY, now)
    said, asked = running_late_says(qapp, window, monkeypatch)
    assert said == f"Starting from {start_24 if twenty_four else start_12} today (Thursday)."
    assert asked == [from_start], "the preview is asked for the start the words name"


def test_running_late_names_the_block_already_in_progress(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    window.session.preferences = {**(window.session.preferences or {}), "clock_24h": False}
    hold_clock(window, THURSDAY, "17:00")
    window.session.blocks = [
        {
            "id": "late-test",
            "title": "Late test",
            "kind": "flexible",
            "duration_min": 60,
            "days": [3],
            "start": "16:45",
            "pinned": False,
        }
    ]
    contexts: list[str] = []

    def inspect(dialog: LateDialog) -> int:
        contexts.append(dialog.context.text())
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(LateDialog, "exec", inspect)
    window._open_late()
    assert contexts == ["Late test, 4:45 PM, moves 30 min later"]


def test_running_late_leaves_homework_that_waits_for_a_time_out_of_the_replan(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    session = window.session
    timed = {
        "id": "essay-1", "title": "Essay", "kind": "flexible", "category": "work",
        "assignment_id": "essay", "start": "16:00", "duration_min": 60, "days": [0],
    }
    waiting = {**timed, "id": "essay-2", "start": None}
    fixed = {"id": "gym", "title": "Gym", "kind": "locked", "category": "extra", "start": "18:00",
             "duration_min": 60, "days": [0]}
    session.blocks = [timed, waiting, fixed]
    assert [block["id"] for block in session._late_blocks()] == ["essay-1", "gym"]
