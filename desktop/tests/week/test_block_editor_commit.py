"""What the window does when the block editor closes: "This day only" with "I missed it" marks that one
day and saves, and an edited block keeps any minute the student typed."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths, QTime
from PySide6.QtWidgets import QApplication, QDialog

from backend.tests.fake_clock import FakeClock
from desktop.native.widgets import BlockDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-block-editor-commit"])


def settled(qapp: QApplication, window: NativeWindow) -> None:
    wait_until(qapp, lambda: not window.session.busy and not window.session.dirty)


def school() -> dict:
    return {
        "id": "school",
        "title": "School",
        "kind": "locked",
        "category": "class",
        "start": "08:00",
        "duration_min": 390,
        "days": [0, 1, 2, 3, 4],
    }


def soccer() -> dict:
    return {
        "id": "soccer",
        "title": "Soccer",
        "kind": "locked",
        "start": "07:00",
        "duration_min": 60,
        "days": [0],
    }


def saved(qapp: QApplication, window: NativeWindow, *blocks: dict) -> None:
    for block in blocks:
        window.session.add_block(block)
    window.session.save()
    settled(qapp, window)


def student(dialog: QDialog, monkeypatch: pytest.MonkeyPatch, steps: Callable[[], None]) -> None:
    """Stand in for the student while the dialog is open, then return as exec() would."""

    def run() -> int:
        dialog.show()
        steps()
        return dialog.result()

    monkeypatch.setattr(dialog, "exec", run, raising=False)


def test_this_day_only_plus_missed_marks_that_one_day_and_saves(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ "This day only" gives Wednesday a new id. The replan was asked for the old id and did nothing, and
    the window returned before saving, so the split stayed an unsaved draft."""
    saved(qapp, window, school())
    dialog = BlockDialog(window, window.session.blocks[0], occurrence_day=2)

    def steps() -> None:
        dialog.scope_occurrence.setChecked(True)
        dialog.missed.setChecked(True)
        dialog.accept()

    student(dialog, monkeypatch, steps)
    window._commit_block(dialog)
    settled(qapp, window)
    by_days = {tuple(block["days"]): block for block in window.session.blocks}
    assert sorted(by_days) == [(0, 1, 3, 4), (2,)]
    # The API leaves missed_days out of a block that has none.
    assert by_days[(2,)].get("missed_days") == [2]
    assert by_days[(0, 1, 3, 4)].get("missed_days") is None
    assert window.session.revision == 2, "the split and the missed day reached the backend"


def test_the_block_editor_saves_any_minute_and_shows_it_back(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    """18:37 to 19:22 was taken by the editor and refused by the backend after Save."""
    # A start before now is refused, so the clock sits at the start of the open week, where Monday is ahead.
    clock.set(datetime.fromisoformat(window.session.week_start))
    saved(qapp, window, soccer())
    dialog = BlockDialog(window, soccer())

    def steps() -> None:
        dialog.start.setTime(QTime(18, 37))
        dialog.end.setTime(QTime(19, 22))
        dialog.accept()

    student(dialog, monkeypatch, steps)
    window._commit_block(dialog)
    settled(qapp, window)
    window.session.load_week(window.session.week_start, discard=True)
    settled(qapp, window)
    stored = next(block for block in window.session.blocks if block["id"] == "soccer")
    assert (stored["start"], stored["duration_min"]) == ("18:37", 45)
    again = BlockDialog(window, stored)
    assert (again.start.time().toString("HH:mm"), again.end.time().toString("HH:mm")) == ("18:37", "19:22")
    assert again.duration_line.text() == "45 min"
