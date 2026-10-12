"""0.19.2 QA lane A: a question sheet's buttons never cut their words, Skip's "Fix them" puts the keyboard
back on the time, a time box's problem line takes its own row instead of stretching the row it is in, and
the Setup side list says Skipped in its accessible name.

Sizes come from font metrics and size hints, never fixed pixels, so the offscreen font does not decide."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QRect, Qt, QTime, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from desktop.native.setup import DONE, SKIPPED, WEEK, SetupPage
from desktop.native.weekmodel import set_clock_24h
from desktop.native.widgets import BlockDialog, ConfirmSheet
from desktop.tests.test_dialogs_look import shown, styled
from desktop.tests.test_regress_item0_time_boxes import _up, enter, press, state, type_text
from desktop.tests.window_support import free, qapp  # noqa: F401

SKIP_QUESTION = (
    ("skip", "Skip without School", "outlined"),
    ("keep", "Keep School and go on", ""),
)
THREE = (
    ("stay", "Cancel", "outlined"),
    ("week", "This week only", ""),
    ("every", "This week and later", "danger"),
)
FOUR = (
    ("stay", "Cancel", "outlined"),
    ("day", "This day only", ""),
    ("week", "This week only", ""),
    ("every", "This week and later", "danger"),
)


def _sheet(qapp: QApplication, answers, width: int, text: str = "normal") -> tuple[QWidget, ConfirmSheet]:
    parent, _palette = styled(qapp, text=text)
    parent.resize(width, 800)
    qapp.processEvents()
    sheet = ConfirmSheet(parent, "Question?", "Which one?", answers, default=answers[0][0])
    shown(qapp, sheet)
    for _ in range(4):
        qapp.processEvents()
    return parent, sheet


def _rows(sheet: ConfirmSheet, answers) -> set[int]:
    return {
        sheet.buttons[key].mapTo(sheet.card, sheet.buttons[key].rect().topLeft()).y() for key, *_ in answers
    }


def _gone(*widgets: QWidget) -> None:
    for widget in widgets:
        widget.hide()
        free(widget)


@pytest.mark.parametrize("answers", [SKIP_QUESTION, THREE, FOUR], ids=["two", "three", "four"])
@pytest.mark.parametrize("text", ["normal", "large"])
@pytest.mark.parametrize("window", [1280, 900, 640, 480])
def test_every_answer_is_as_wide_as_its_words_side_by_side_or_stacked(
    qapp: QApplication, answers, text: str, window: int
) -> None:
    parent, sheet = _sheet(qapp, answers, window, text)
    try:
        buttons = [sheet.buttons[key] for key, _words, _kind in answers]
        for button in buttons:
            words = button.fontMetrics().horizontalAdvance(button.text())
            assert button.width() >= max(button.sizeHint().width(), words + 2), (
                f"{button.text()!r} is {button.width()} px for {words} px of words"
            )
        card = sheet.card.mapTo(parent, sheet.card.rect().topLeft())
        assert QRect(card, sheet.card.size()).intersected(parent.rect()) == QRect(card, sheet.card.size()), (
            "the sheet stays inside its window"
        )
        left = [button.mapTo(sheet.card, button.rect().topLeft()) for button in buttons]
        for button, at in zip(buttons, left, strict=True):
            inside = at.x() >= 0 and at.x() + button.width() <= sheet.card.width()
            assert inside, f"{button.text()!r} leaves the card"
        rows = {at.y() for at in left}
        if len(rows) == 1:
            assert left == sorted(left, key=lambda at: at.x()), "side by side keeps the quietest first"
        else:
            assert len(rows) == len(buttons), "stacked is one answer per row"
            assert left == sorted(left, key=lambda at: at.y()), "stacked keeps the order, the filled one last"
            assert buttons[-1].mapTo(sheet.card, buttons[-1].rect().bottomLeft()).y() <= sheet.card.height()
    finally:
        _gone(sheet, parent)


def test_a_wide_window_holds_the_answers_in_one_row_and_a_narrow_one_stacks_them(qapp: QApplication) -> None:
    parent, sheet = _sheet(qapp, FOUR, 1280)
    try:
        ys = _rows(sheet, FOUR)
        assert len(ys) == 1, "four answers fit side by side in a 1280 px window"
    finally:
        _gone(sheet, parent)
    parent, sheet = _sheet(qapp, FOUR, 480)
    try:
        ys = _rows(sheet, FOUR)
        assert len(ys) == 4, "four answers do not fit side by side in a 480 px window"
    finally:
        _gone(sheet, parent)


def test_stacking_keeps_the_default_answer_and_the_tab_order(qapp: QApplication) -> None:
    parent, sheet = _sheet(qapp, THREE, 480)
    try:
        assert sheet.buttons["stay"].isDefault()
        assert QApplication.focusWidget() is sheet.buttons["stay"], "the keyboard starts on the default"
        order = []
        for _ in range(3):
            order.append(QApplication.focusWidget().property("answer"))
            QTest.keyClick(sheet, Qt.Key.Key_Tab)
        assert order == ["stay", "week", "every"]
    finally:
        _gone(sheet, parent)


# Skip -> Fix them --------------------------------------------------------------------------------


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

    def answer() -> None:
        sheet = QApplication.activeModalWidget()
        if not isinstance(sheet, ConfirmSheet):
            QTimer.singleShot(20, answer)
            return
        seen.append(sheet)
        if how == "escape":
            QTest.keyClick(sheet, Qt.Key.Key_Escape)
        else:
            sheet.buttons[how].click()

    QTimer.singleShot(20, answer)
    setup.skip.click()
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
        QTest.qWait(20)
        _gone(setup)


def test_skip_without_school_goes_on_and_keep_goes_on_with_school(qapp: QApplication) -> None:
    setup = _week_page(qapp)
    try:
        _bad_school_end(setup)
        _answer_skip_question(setup, "skip")
        assert setup.step != WEEK, "Skip without School leaves the step"
    finally:
        QTest.qWait(20)
        _gone(setup)


# A problem line takes its own row ------------------------------------------------------------------


def _rect_in(widget: QWidget, top: QWidget) -> QRect:
    return QRect(widget.mapTo(top, widget.rect().topLeft()), widget.size())


def _overlapping(top: QWidget, line: QWidget) -> list[str]:
    """Visible widgets that share pixels with `line` without holding it or being held by it."""
    mine = _rect_in(line, top)
    out = []
    for other in top.findChildren(QWidget):
        if other is line or not other.isVisible() or other.isAncestorOf(line) or line.isAncestorOf(other):
            continue
        if other.window() is not top.window() or other.width() <= 0:
            continue
        if mine.intersects(_rect_in(other, top)):
            name = f"{other.metaObject().className()}#{other.objectName()}"
            out.append(f"{name} {_rect_in(other, top).getRect()} vs {mine.getRect()}")
    return out


def _problem_line(box) -> QWidget:
    return box._line


@pytest.mark.parametrize("which", ["school", "activity"])
def test_a_problem_under_a_setup_end_time_leaves_its_row_where_it_was(qapp: QApplication, which: str) -> None:
    setup = _week_page(qapp)
    try:
        if which == "school":
            times, days = setup.school_times, setup.school_days
        else:
            row = setup.activities[0]
            row.name.setText("Soccer")
            row.days.set_days([1])
            times, days = row.times, row.days
        qapp.processEvents()
        before = {
            "start": _rect_in(times.start, setup),
            "end": _rect_in(times.end, setup),
            "chip": _rect_in(days.buttons[0], setup),
        }
        times.start.setTime(QTime(8, 30))
        before["start"] = _rect_in(times.start, setup)
        end = times.end
        enter(end, "tab-in")
        type_text(end, "3:15a")
        press(end, Qt.Key.Key_Tab)
        for _ in range(4):
            qapp.processEvents()
        assert end.problem()
        line = _problem_line(end)
        assert line.isVisible()
        assert _rect_in(times.start, setup).topLeft() == before["start"].topLeft(), "Start did not move"
        chip = _rect_in(days.buttons[0], setup)
        assert chip.topLeft() == before["chip"].topLeft(), "the day chips did not move"
        assert _rect_in(end, setup).topLeft() == before["end"].topLeft(), "End did not move"
        assert end.width() == before["end"].width(), "End kept its width"
        assert _rect_in(line, setup).top() >= _rect_in(end, setup).bottom(), "the line is under End"
        assert not _overlapping(setup, line), _overlapping(setup, line)
    finally:
        QTest.qWait(20)
        _gone(setup)


def test_a_problem_under_school_pushes_the_activities_below_it_down(qapp: QApplication) -> None:
    setup = _week_page(qapp)
    try:
        setup.activities[0].name.setText("Soccer")
        qapp.processEvents()
        below = _rect_in(setup.activities[0], setup)
        _bad_school_end(setup)
        for _ in range(4):
            qapp.processEvents()
        line = _problem_line(setup.school_times.end)
        assert _rect_in(setup.activities[0], setup).top() >= below.top() + line.height() - 1, (
            "the activity section moved down by the line's height"
        )
        assert _rect_in(line, setup).bottom() <= _rect_in(setup.activities[0], setup).top()
    finally:
        QTest.qWait(20)
        _gone(setup)


def test_the_problem_line_goes_when_the_problem_is_fixed(qapp: QApplication) -> None:
    setup = _week_page(qapp)
    try:
        resting = _rect_in(setup.activities[0], setup)
        _bad_school_end(setup)
        end = setup.school_times.end
        assert _rect_in(setup.activities[0], setup).top() > resting.top()
        setup.school_times.set_span("08:30", 60)
        end._mend()
        for _ in range(4):
            qapp.processEvents()
        assert _rect_in(setup.activities[0], setup).top() == resting.top()
    finally:
        QTest.qWait(20)
        _gone(setup)


def test_the_block_editor_start_problem_takes_a_row_between_start_and_duration(qapp: QApplication) -> None:
    set_clock_24h(False)
    window, _palette = styled(qapp)
    dialog = BlockDialog(window, day=1, start="16:00", duration_min=60)
    shown(qapp, dialog)
    try:
        start, end = dialog.start, dialog.end
        resting_end = _rect_in(end, dialog)
        resting_start = _rect_in(start, dialog)
        enter(start, "tab-in")
        type_text(start, "abc")
        press(start, Qt.Key.Key_Tab)
        for _ in range(4):
            qapp.processEvents()
        assert start.problem()
        line = _problem_line(start)
        assert line.isVisible()
        assert _rect_in(start, dialog) == resting_start, "Start stays"
        assert _rect_in(end, dialog) == resting_end, "End stays"
        mine = _rect_in(line, dialog)
        assert mine.top() >= _rect_in(start, dialog).bottom()
        for other in (dialog.duration_line, dialog.category, end):
            assert not mine.intersects(_rect_in(other, dialog)), other.objectName() or type(other).__name__
        assert not _overlapping(dialog, line), _overlapping(dialog, line)
        assert mine.right() <= dialog.rect().right(), "the line stays inside the sheet"
    finally:
        QTest.qWait(20)
        _gone(dialog, window)


# The side list says it in words ----------------------------------------------------------------------


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
        QTest.qWait(20)
        _gone(setup)
