"""Setup's Your week step: Skip with a time that cannot be kept asks, and Fix them (or Esc) puts the
keyboard on the End time with all of it selected; a time box's problem line shows under the box and
goes when it is fixed; the side list says Skipped in its accessible name. Where the problem line sits
and what it leaves alone are looks: pictures/_sheets_g13.py.

Sizes are never read here, so the offscreen font does not decide anything."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths, Qt, QTime
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from desktop.native.setup import DONE, SKIPPED, WEEK, SetupPage
from desktop.native.weekmodel import set_clock_24h
from desktop.native.widgets import BlockDialog, ConfirmSheet
from desktop.tests.sheets.support_dialogs import school, shown, styled, when_open
from desktop.tests.test_regress_item0_time_boxes import _up, enter, press, state, type_text
from desktop.tests.window_support import free


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-setup-skip-test"])


def _gone(*widgets: QWidget) -> None:
    for widget in widgets:
        widget.hide()
        free(widget)


def _week_page(qapp: QApplication) -> SetupPage:
    set_clock_24h(False)
    setup = SetupPage()
    setup.motion = "off"
    setup.resize(1100, 720)
    setup.open(state())
    setup._show(WEEK)
    _up(qapp, setup)
    return setup


def _bad_school_end(setup: SetupPage) -> None:
    setup.school_times.start.setTime(QTime(8, 30))
    end = setup.school_times.end
    enter(end, "tab-in")
    type_text(end, "3:15a")
    press(end, Qt.Key.Key_Tab)
    assert end.problem()


def _answer_skip_question(setup: SetupPage, how: str) -> list[ConfirmSheet]:
    seen: list[ConfirmSheet] = []

    def answer(sheet: ConfirmSheet) -> None:
        assert isinstance(sheet, ConfirmSheet), "Skip asks on an answer sheet"
        seen.append(sheet)
        if how == "escape":
            QTest.keyClick(sheet, Qt.Key.Key_Escape)
        else:
            sheet.buttons[how].click()

    check = when_open(answer)
    setup.skip.click()
    check()
    for _ in range(6):
        QApplication.processEvents()
    return seen


@pytest.mark.parametrize("how", ["fix", "escape"])
def test_fix_them_and_escape_put_the_keyboard_on_the_end_time_with_all_of_it_selected(
    qapp: QApplication, how: str
) -> None:
    setup = _week_page(qapp)
    try:
        _bad_school_end(setup)
        seen = _answer_skip_question(setup, how)
        assert seen, "Skip asked"
        assert setup.step == WEEK, "Fix them stays on the step"
        end = setup.school_times.end
        assert QApplication.focusWidget() in (end, end.lineEdit()), "the keyboard is on the End time"
        assert end.lineEdit().selectedText() == end.lineEdit().text() != ""
    finally:
        _gone(setup)


def test_skip_without_school_goes_on_and_keep_goes_on_with_school(qapp: QApplication) -> None:
    setup = _week_page(qapp)
    try:
        _bad_school_end(setup)
        _answer_skip_question(setup, "skip")
        assert setup.step != WEEK, "Skip without School leaves the step"
    finally:
        _gone(setup)


@pytest.mark.parametrize("which", ["school", "activity"])
def test_a_bad_end_time_says_so_in_a_line_under_the_box(qapp: QApplication, which: str) -> None:
    setup = _week_page(qapp)
    try:
        if which == "school":
            times = setup.school_times
        else:
            row = setup.activities[0]
            row.name.setText("Soccer")
            row.days.set_days([1])
            times = row.times
        qapp.processEvents()
        times.start.setTime(QTime(8, 30))
        end = times.end
        enter(end, "tab-in")
        type_text(end, "3:15a")
        press(end, Qt.Key.Key_Tab)
        for _ in range(4):
            qapp.processEvents()
        assert end.problem()
        assert end._line.isVisible()
    finally:
        _gone(setup)


def test_the_problem_line_goes_when_the_problem_is_fixed(qapp: QApplication) -> None:
    setup = _week_page(qapp)
    try:
        _bad_school_end(setup)
        end = setup.school_times.end
        assert end._line.isVisible()
        setup.school_times.set_span("08:30", 60)
        end._mend()
        for _ in range(4):
            qapp.processEvents()
        assert end.problem() == ""
        assert not end._line.isVisible()
    finally:
        _gone(setup)


def test_the_block_editors_bad_start_says_so_in_a_line_under_the_box(qapp: QApplication) -> None:
    set_clock_24h(False)
    window, _palette = styled(qapp)
    # Add is stepped (What / When / Category); Edit stays one page with Start beside End.
    dialog = BlockDialog(window, school(), occurrence_day=1)
    shown(qapp, dialog)
    try:
        start = dialog.start
        enter(start, "tab-in")
        type_text(start, "abc")
        press(start, Qt.Key.Key_Tab)
        for _ in range(4):
            qapp.processEvents()
        assert start.problem()
        assert start._line.isVisible()
    finally:
        _gone(dialog, window)


def test_the_side_list_names_each_steps_state_in_its_accessible_name(qapp: QApplication) -> None:
    set_clock_24h(False)
    setup = SetupPage()
    setup.motion = "off"
    setup.resize(1100, 720)
    setup.open(state())
    _up(qapp, setup)
    try:
        setup._show(WEEK)
        setup.skip.click()
        for _ in range(4):
            qapp.processEvents()
        names = [item.accessibleName() for item in setup.rail_items]
        assert names[1] == "Step 2: Your week, skipped"
        assert names[0] == "Step 1: Style, done"
        assert names[2].startswith("Step 3: ") and names[2].endswith(", current step")
        assert names[-1] == "Step 6: Done"
        assert SKIPPED == "skipped" and DONE > WEEK
    finally:
        _gone(setup)
