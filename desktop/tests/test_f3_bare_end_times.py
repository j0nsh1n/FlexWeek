"""F3 of the 0.19.0 QA round: on the 12-hour clock an end box reads a time typed without AM or PM by its
start, and an end at or before its start is said under the end box, never only in a form's footer."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt, QTime
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from desktop.native.weekmodel import set_clock_24h
from desktop.native.widgets import BlockDialog, SchoolHoursDialog
from desktop.tests.test_regress_item0_time_boxes import _setup, _up, enter, press, type_text
from desktop.tests.window_support import free, qapp  # noqa: F401


@pytest.fixture()
def editor(qapp: QApplication):
    made: list = []

    def open_editor(start: str, twelve: bool = True) -> BlockDialog:
        set_clock_24h(not twelve)
        # Edit stays one page (Add is stepped). F3 is the End box, which Add hides until When.
        dialog = BlockDialog(
            None,
            {
                "id": "club",
                "title": "Club",
                "kind": "locked",
                "start": start,
                "duration_min": 60,
                "days": [1],
                "category": "extra",
            },
        )
        _up(qapp, dialog)
        made.append(dialog)
        return dialog

    yield open_editor
    QTest.qWait(20)
    for dialog in made:
        dialog.hide()
        free(dialog)


def typed_end(field, text: str) -> None:
    # Form 21031111: Start and End sit side by side under their captions. Tab-from-previous
    # can miss End; a click is how a student reaches it.
    enter(field, "click-middle")
    type_text(field, text)
    press(field, Qt.Key.Key_Tab)


BARE_ENDS = [
    ("08:30", "1230", 12 * 60 + 30),
    ("08:30", "315", 15 * 60 + 15),
    ("08:30", "11", 11 * 60),
    ("13:00", "4", 16 * 60),
]


@pytest.mark.parametrize(("start", "typed", "minutes"), BARE_ENDS)
def test_a_bare_end_takes_the_half_that_ends_soonest_after_the_start(editor, start, typed, minutes) -> None:
    dialog = editor(start)
    typed_end(dialog.end, typed)
    assert dialog.end.minutes() == minutes
    assert dialog.end.problem() == ""


def test_a_written_half_is_kept_and_an_end_before_start_says_so_under_end(editor) -> None:
    dialog = editor("08:30")
    typed_end(dialog.end, "3:15 am")
    assert dialog.end.minutes() == 3 * 60 + 15
    assert dialog.end.problem() == "End needs to be later than Start (8:30 AM)."
    assert dialog.duration_line.text() == "", "the same sentence is not said twice"


def test_after_a_9_pm_start_neither_half_works_and_the_problem_shows(editor) -> None:
    dialog = editor("21:00")
    typed_end(dialog.end, "1230")
    assert dialog.end.problem() == "End needs to be later than Start (9:00 PM)."
    dialog.start.setTime(QTime(10, 0))
    assert dialog.end.problem() == "", "a start moved before the end takes the problem back"


def test_nothing_is_said_while_the_end_is_still_being_typed(editor) -> None:
    dialog = editor("21:00")
    enter(dialog.end, "tab-in")
    type_text(dialog.end, "114")
    assert dialog.end.problem() == ""


def test_the_24_hour_clock_reads_a_bare_time_as_written(editor) -> None:
    dialog = editor("08:30", twelve=False)
    typed_end(dialog.end, "3:15")
    assert dialog.end.minutes() == 3 * 60 + 15
    assert "End needs to be later than Start" in dialog.end.problem()


@pytest.mark.parametrize("which", ["school-end", "activity-end"])
def test_setup_reads_a_bare_end_by_its_start(qapp: QApplication, which: str) -> None:
    set_clock_24h(False)
    box = _setup(qapp, which)
    try:
        typed_end(box.field, "315")
        assert box.field.minutes() == 15 * 60 + 15
        assert box.field.problem() == ""
    finally:
        QTest.qWait(20)
        for widget in box.owned:
            widget.hide()
            free(widget)


def test_setup_offers_the_other_half_and_next_stays_on_the_end(qapp: QApplication) -> None:
    set_clock_24h(False)
    box = _setup(qapp, "school-end")
    setup = box.top
    try:
        setup.school_times.start.setTime(QTime(8, 30))
        typed_end(box.field, "3:15a")
        assert box.field.problem() == (
            "School ends at 3:15 AM, before it starts at 8:30 AM. Did you mean 3:15 PM?"
        )
        step = setup._step
        setup.next.click()
        assert setup._step == step and box.field.hasFocus(), "Next keeps the keyboard on End"
        use = next(b for b in setup.findChildren(QPushButton, "clockErrorUse") if b.isVisible())
        assert use.text() == "Use 3:15 PM"
        use.click()
        assert box.field.minutes() == 15 * 60 + 15
        assert box.field.problem() == ""
    finally:
        QTest.qWait(20)
        for widget in box.owned:
            widget.hide()
            free(widget)


def test_school_hours_reads_a_bare_end_by_its_start(qapp: QApplication) -> None:
    set_clock_24h(False)
    dialog = SchoolHoursDialog(None, {"start": "08:30", "duration_min": 60, "days": [0]})
    _up(qapp, dialog)
    try:
        typed_end(dialog.times.end, "315")
        assert dialog.times.end.minutes() == 15 * 60 + 15
    finally:
        QTest.qWait(20)
        dialog.hide()
        free(dialog)


def test_skip_on_an_unchanged_week_asks_nothing_and_the_summary_says_skipped(qapp: QApplication) -> None:
    """F3b: Skip asks only about what the student changed; a skipped Your week reads "skipped" on the
    last page, not "Nothing fixed yet"."""
    from desktop.native.setup import DONE, WEEK, SetupPage
    from desktop.tests.test_regress_item0_time_boxes import state

    setup = SetupPage()
    setup.motion = "off"
    setup.open(state())
    setup._show(WEEK)
    _up(qapp, setup)
    try:
        setup.skip.click()
        assert QApplication.activeModalWidget() is None, "nothing was typed, so nothing is asked"
        assert setup.step != WEEK
        setup._show(DONE)
        week = setup.summary_rows[1][1].text()
        assert week == "skipped"
    finally:
        QTest.qWait(20)
        setup.hide()
        free(setup)
