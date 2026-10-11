"""Regression for QA's F3b (fix-specs-0190.md): Skip on Setup's Your week throws School away without asking,
marks the step done, and a blocked Next leaves the keyboard where it was.

On SetupPage itself (the item 0 suite's `_setup`: School 8:00 to 18:00 or to a bad end), with clicks and
keys through the window system. Known failures are xfail(strict=True).
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt, QTime, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from desktop.native.setup import RAIL, WEEK
from desktop.tests.regress184.test_regress_item0_time_boxes import _setup
from desktop.tests.window_support import free, qapp  # noqa: F401

KNOWN_ASK = "known failure (F3b): Skip runs _leave(keep=False) at once; nothing asks, School is dropped"
KNOWN_MARK = "known failure (F3b): a skipped step is marked Done in the side list"
KNOWN_FOCUS = "known failure (F3b): a blocked Next leaves the keyboard on Next, not on the bad End box"


@pytest.fixture()
def school(qapp):
    made = []

    def make(bad: bool):
        box = _setup(qapp, "school-end")
        made.append(box)
        box.top.school_times.start.setTime(QTime(8, 30))
        box.field.setTime(QTime(3, 15) if bad else QTime(15, 15))
        qapp.processEvents()
        return box

    yield make
    QTest.qWait(20)
    for box in made:
        for widget in box.owned:
            widget.hide()
            free(widget)


def click_skip(qapp, setup) -> list[str]:
    """Click Skip; a question that opens is read and left with Escape. Returns its buttons' words."""
    asked: list[str] = []

    def look() -> None:
        sheet = QApplication.activeModalWidget()
        if sheet is not None:
            asked.append(" | ".join(b.text() for b in sheet.findChildren(QPushButton) if b.isVisible()))
            QTest.keyClick(sheet.windowHandle(), Qt.Key.Key_Escape)

    QTimer.singleShot(250, look)
    QTest.mouseClick(setup.skip, Qt.MouseButton.LeftButton)
    for _ in range(10):
        QTest.qWait(50)
    return asked


def test_f3b_skip_with_a_bad_school_asks_and_escape_means_fix_them(qapp, school) -> None:
    box = school(bad=True)
    asked = click_skip(qapp, box.top)
    assert asked and "Fix them" in asked[0] and "Skip without School" in asked[0], asked
    assert box.top._step == WEEK
    assert QApplication.focusWidget() in (box.field, box.field.lineEdit())


def test_f3b_skip_with_a_good_school_asks_and_escape_keeps_school(qapp, school) -> None:
    box = school(bad=False)
    asked = click_skip(qapp, box.top)
    assert asked and "Keep School and go on" in asked[0], asked
    assert [b["title"] for b in box.top.week_blocks()] == ["School"]
    assert box.top._step != WEEK  # kept and went on


def test_f3b_a_skipped_step_is_marked_skipped_not_done(qapp, school) -> None:
    box = school(bad=False)
    box.top._leave(box.top._after(WEEK), keep=False)  # what "Skip without School" ends in
    qapp.processEvents()
    index = next(i for i, (_name, steps) in enumerate(RAIL) if WEEK in steps)
    said = box.top.rail_items[index].accessibleDescription()
    assert said == "Skipped", repr(said)


def test_f3b_a_blocked_next_puts_the_keyboard_on_end_with_its_time_selected(qapp, school) -> None:
    box = school(bad=True)
    box.top.next.setFocus(Qt.FocusReason.TabFocusReason)
    QTest.keyClick(box.top.windowHandle(), Qt.Key.Key_Space)
    qapp.processEvents()
    assert box.top._step == WEEK, "Next was not blocked"
    line = box.field.lineEdit()
    assert QApplication.focusWidget() in (box.field, line), f"focus on {QApplication.focusWidget()}"
    assert line.selectedText() == line.text()
