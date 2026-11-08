"""Right-clicking a block in the week: the block menu offers Copy, and deleting one time of a
homework that has more than one asks which time."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from copy import deepcopy

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialog

from desktop.native.widgets import ConfirmSheet
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.week.support_weekview import essay_week, menus  # noqa: F401
from desktop.tests.window_support import qapp, settled  # noqa: F401


def two_essay_sessions(window: NativeWindow) -> tuple[dict, dict]:
    session = window.session
    first = next(item for item in session.blocks if item.get("assignment_id") == "math")
    extra = deepcopy(first)
    extra["id"] = "math-2"
    extra["days"] = [4]
    extra["start"] = "16:00"
    session.blocks.append(extra)
    return first, session.assignments["math"]


def test_the_block_menu_includes_copy_and_one_delete(
    qapp: QApplication,
    essay_week: NativeWindow,
    menus: dict,
) -> None:
    window = essay_week
    hours = window.week_table.hours
    essay = next(b for b in window.session.blocks if b.get("assignment_id") == "math")
    box = hours.block_rect(essay["id"], 2)
    assert box is not None
    window._block_menu(essay["id"], 2, box.center())
    hours.hand.step = 15
    hours.reveal(1, 17 * 60, 17 * 60 + 30)
    qapp.processEvents()
    window._spot_menu(1, 17 * 60, hours.point_for(1, 17 * 60))
    assert len(menus["rows"]) == 2
    block_rows = menus["rows"][0]
    assert "Copy\tCtrl+C" in block_rows
    assert "Delete homework" not in block_rows
    assert sum("Delete" in r for r in block_rows) == 1


def test_deleting_one_time_of_homework_from_the_menu_asks_which(
    qapp: QApplication,
    essay_week: NativeWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = essay_week
    block, assignment = two_essay_sessions(window)

    def run(sheet: ConfirmSheet) -> int:
        words = {button.text() for button in sheet.buttons.values()}
        assert "This time" in words and "Delete" in words
        chosen = next(key for key, button in sheet.buttons.items() if button.text() == "This time")
        sheet.buttons[chosen].click()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(ConfirmSheet, "exec", run)
    window._delete_from_block_menu(block, assignment, 2)
    settled(qapp, window)
    kept = [item for item in window.session.blocks if item.get("assignment_id") == "math"]
    assert len(kept) == 1 and kept[0]["days"] == [4]
    assert "math" in window.session.assignments


def test_deleting_the_whole_homework_from_the_menu_uses_the_editors_words(
    qapp: QApplication,
    essay_week: NativeWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = essay_week
    block, assignment = two_essay_sessions(window)
    questions: list[str] = []

    def run(sheet: ConfirmSheet) -> int:
        questions.append(sheet.question.text())
        chosen = next(key for key, button in sheet.buttons.items() if button.text() == "Delete")
        sheet.buttons[chosen].click()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(ConfirmSheet, "exec", run)
    window._delete_from_block_menu(block, assignment, 2)
    settled(qapp, window)
    assert questions == [
        "Delete Math worksheet? Its times on the calendar go too, in every week. You can undo this."
    ]
    assert "math" not in window.session.assignments
