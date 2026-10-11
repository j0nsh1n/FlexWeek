"""Regression for the QA team's confirmed 0.19.0 bugs (Coder's /workspace/coder190/fix-specs-0190.md):
F3 (a bare end time on the 12-hour clock reads as AM), T1 (Delete in a repeating block's editor defaults
to every day) and T-W1 (a 12-hour range ending at midnight loses its first AM/PM).

Keys go through the window system (QTest on the window's QWindow), as in the 0.18.4 suite. The clock
setting is put back to 24-hour after every test by desktop/tests/conftest.py. Known failures are
xfail(strict=True).
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt, QTime
from PySide6.QtTest import QTest

from desktop.native.weekmodel import range_label, set_clock_24h
from desktop.native.widgets import BlockDialog
from desktop.tests.regress184.test_regress_item0_time_boxes import _setup, _up, enter, press, type_text
from desktop.tests.window_support import free, qapp  # noqa: F401

KNOWN_F3 = (
    "known failure (F3): read_clock reads a bare '3:15' as 3:15 AM on the 12-hour clock, even after a "
    "morning Start"
)
KNOWN_F3B = "known failure (F3.B): an End at or before Start shows no problem line under End"
KNOWN_T1 = "known failure (T1): BlockDialog sets scope_choice to 'Every selected day' (index 1) by default"
KNOWN_TW1 = "known failure (T-W1): range_label(540, 1440) is '9–12 AM'; the start loses its AM"


@pytest.fixture()
def block_editor(qapp):
    made: list = []

    def open_editor(start: str, twelve: bool) -> BlockDialog:
        set_clock_24h(not twelve)
        dialog = BlockDialog(None, day=1, start=start, duration_min=60)
        _up(qapp, dialog)
        made.append(dialog)
        return dialog

    yield open_editor
    QTest.qWait(20)
    for dialog in made:
        dialog.hide()
        free(dialog)


def type_end(dialog: BlockDialog, text: str) -> None:
    enter(dialog.end, "tab-in")  # Tab from Start selects the whole End, as a student does
    type_text(dialog.end, text)
    press(dialog.end, Qt.Key.Key_Tab)


@pytest.mark.xfail(strict=True, reason=KNOWN_F3)
@pytest.mark.parametrize("typed", ["3:15", "315"])
def test_f3_block_editor_bare_end_after_830_am_reads_pm(block_editor, typed) -> None:
    dialog = block_editor("08:30", twelve=True)
    type_end(dialog, typed)
    assert dialog.end.minutes() == 15 * 60 + 15, dialog.end.lineEdit().text()


@pytest.mark.xfail(strict=True, reason=KNOWN_F3)
def test_f3_setup_school_bare_end_after_830_am_reads_pm(qapp) -> None:
    set_clock_24h(False)
    box = _setup(qapp, "school-end")
    try:
        box.field.setFocus()
        box.field.lineEdit().selectAll()
        type_text(box.field, "3:15")
        press(box.field, Qt.Key.Key_Tab)
        assert box.field.minutes() == 15 * 60 + 15, box.field.lineEdit().text()
    finally:
        QTest.qWait(20)
        for widget in box.owned:
            widget.hide()
            free(widget)


@pytest.mark.xfail(strict=True, reason=KNOWN_F3B)
def test_f3_end_before_a_9_pm_start_shows_the_problem_under_end(block_editor) -> None:
    dialog = block_editor("21:00", twelve=True)
    type_end(dialog, "3:15")
    assert "End needs to be later than Start" in dialog.end.problem(), repr(dialog.end.problem())


def test_f3_guard_24_hour_end_is_unchanged(block_editor) -> None:
    dialog = block_editor("08:30", twelve=False)
    type_end(dialog, "15:15")
    assert dialog.end.time() == QTime(15, 15)


@pytest.mark.xfail(strict=True, reason=KNOWN_T1)
def test_t1_editor_opened_from_one_day_of_a_repeating_block_defaults_to_this_day(qapp) -> None:
    soccer = {"id": "soccer", "title": "Soccer", "kind": "locked", "category": "extra", "start": "16:00",
              "duration_min": 90, "days": [1, 3]}
    dialog = BlockDialog(None, block=soccer, occurrence_day=1)
    try:
        assert dialog.scope_choice.currentIndex() == 0, "Apply to does not default to the narrowest choice"
    finally:
        free(dialog)


@pytest.mark.xfail(strict=True, reason=KNOWN_TW1)
@pytest.mark.parametrize(("start", "mark"), [(9 * 60, "9 AM"), (11 * 60 + 30, "11:30 AM")])
def test_tw1_a_range_ending_at_midnight_keeps_the_starts_mark(start, mark) -> None:
    """Only the start is asserted: "12 AM" vs "midnight" for the end is a 0.19.1 wording call."""
    set_clock_24h(False)
    assert range_label(start, 1440).startswith(mark), range_label(start, 1440)


def test_tw1_guard_same_half_ranges_keep_the_short_form() -> None:
    set_clock_24h(False)
    assert range_label(16 * 60, 17 * 60 + 30) == "4–5:30 PM"
    assert range_label(21 * 60, 1440).startswith("9 PM")
