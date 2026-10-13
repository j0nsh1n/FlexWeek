"""The 1.0.0 form grammar (forms.html, structure=c, grammar on).

A caption sits above each field. A problem is a line as wide as its field, with no frame; a row's
problem is as wide as that row. Buttons are as wide as their words and stack when the row is too
narrow. Account cards show one problem at a time, send the keyboard to that field, and keep their
top when the line appears.

Expected words and geometry are from the demo: caption above the field, `.problem` with no border,
button width at least the words, stack when the row cannot hold them, one error, focus on its field.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt, QTime
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QDateEdit,
    QDialog,
    QFrame,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from desktop.native.devices import PairDialog, RemoveDialog, SyncService
from desktop.native.fields import ClockField, ProblemLine
from desktop.native.look import pack_stylesheet, resolved_palette
from desktop.native.settings import AccountDialog, RestoreDialog
from desktop.native.setup import ActivityRow, HomeworkRow
from desktop.native.widgets import (
    SHEET_PAD,
    AnswerRow,
    AvailabilityDialog,
    BlockDialog,
    ChooseTimeDialog,
    ConfirmSheet,
    HomeworkDialog,
    LateDialog,
    RoutineDialog,
    SchoolHoursDialog,
    SpreadDialog,
    control_art,
)
from desktop.native.work_windows import WorkWindowsEditor
from desktop.tests.test_dialogs_look import shown, soccer, styled
from desktop.tests.test_sign_in_0185 import card_of, go, pump
from desktop.tests.window_support import free, qapp, server, signed_out  # noqa: F401

WEEK = "2026-10-12"
# School's "from" and "to" sit on the time's own line in the demo, so they are not sheet captions.
SKIP_FIELDS = frozenset({"setupTime"})


def _top(widget: QWidget, root: QWidget) -> int:
    return widget.mapTo(root, QPoint(0, 0)).y()


def _left(widget: QWidget, root: QWidget) -> int:
    return widget.mapTo(root, QPoint(0, 0)).x()


def _bottom(widget: QWidget, root: QWidget) -> int:
    return widget.mapTo(root, QPoint(0, widget.height())).y()


def _words(button: QPushButton) -> str:
    return button.text().replace("&", "")


def _ready(app: QApplication, widget: QWidget) -> None:
    """Show `widget` and give it the keyboard, the same way the time-box tests do."""
    widget.show()
    assert QTest.qWaitForWindowExposed(widget.window())
    widget.window().activateWindow()
    app.processEvents()


def _type_over(app: QApplication, field: QWidget, text: str) -> None:
    """Replace what `field` shows, then Tab away, so a clock settles the way a student leaves it."""
    field.setFocus(Qt.FocusReason.TabFocusReason)
    app.processEvents()
    line = field.lineEdit() if hasattr(field, "lineEdit") else field
    line.selectAll()
    window = field.window().windowHandle()
    for char in text:
        QTest.keyClick(window, char)
        app.processEvents()
    QTest.keyClick(window, Qt.Key.Key_Tab)
    app.processEvents()


def _sheets(parent: QWidget) -> list[QDialog]:
    essay = {
        "id": "essay",
        "title": "Essay",
        "estimate_min": 60,
        "due": "2026-10-16",
        "unplanned_min": 60,
    }
    sync = Mock(spec=SyncService)
    sync.pair_start.return_value = None
    return [
        PairDialog(parent, sync, 1),
        RemoveDialog(parent, "Pixel"),
        BlockDialog(parent, soccer(), occurrence_day=3),
        HomeworkDialog(parent, essay, today=WEEK),
        SchoolHoursDialog(parent),
        ChooseTimeDialog(parent, {"id": "essay", "title": "Essay", "duration_min": 45}, WEEK, [0], [], None),
        LateDialog(parent, "You are in class."),
        SpreadDialog(parent, essay, WEEK),
        RoutineDialog(parent, {}, [], WEEK),
        AvailabilityDialog(parent, {}),
        AccountDialog(parent, 4, {"mode": "local", "username": "ada"}),
        ConfirmSheet(
            parent,
            "Delete School?",
            "Delete School on Thursday 15 Oct only?",
            (
                ("stay", "Cancel", "outlined"),
                ("day", "This day only", ""),
                ("week", "This week only", "tint"),
                ("later", "This week and later", "danger"),
            ),
            default="stay",
        ),
        RestoreDialog(parent, [], None, {}),
    ]


def _inputs(root: QWidget) -> list[QWidget]:
    kinds = (QLineEdit, QPlainTextEdit, QComboBox, QAbstractSpinBox, QDateEdit)
    found = []
    for kind in kinds:
        for widget in root.findChildren(kind):
            parent = widget.parentWidget()
            inner = isinstance(parent, (QAbstractSpinBox, QComboBox))
            if inner or not widget.isVisibleTo(root) or widget.objectName() in SKIP_FIELDS:
                continue
            found.append(widget)
    return found


def _aligns_with(field: QWidget) -> QWidget:
    """The control a caption sits over. A stepper's number is inset by its minus button, and the
    caption lines up with the stepper, which is the control."""
    parent = field.parentWidget()
    if parent is not None and parent.objectName() == "stepper":
        return parent
    return field


def _caption_for(field: QWidget, root: QWidget) -> QLabel | None:
    labels = [
        label
        for label in root.findChildren(QLabel)
        if label.objectName() in ("fieldLabel", "homeworkPrompt", "blockPrompt")
        and label.isVisibleTo(root)
        and label.text()
    ]
    buddy = next((label for label in labels if label.buddy() is field), None)
    if buddy is not None:
        return buddy
    overlapping = [
        label
        for label in labels
        if _bottom(label, root) <= _top(field, root)
        and _left(label, root) <= _left(field, root) + 4
        and _left(label, root) + label.width() > _left(field, root)
    ]
    if not overlapping:
        return None
    return max(overlapping, key=lambda label: _bottom(label, root))


def test_the_problem_rule_has_no_frame(qapp: QApplication) -> None:  # noqa: F811
    """forms.html `.problem` is the error colour and the words, with no border."""
    palette = resolved_palette("light-frost", False, None, "default")
    sheet = pack_stylesheet("light-frost", False, None, "default", palette, control_art(palette))
    mark = 'QFrame[problem="true"]'
    rule = sheet[sheet.index(mark) : sheet.index("}", sheet.index(mark)) + 1]
    assert rule == 'QFrame[problem="true"] { background: transparent; border: 0; padding: 0; }'


def test_a_fields_problem_is_as_wide_as_the_field_and_has_no_frame(qapp: QApplication) -> None:  # noqa: F811
    host, _palette = styled(qapp)
    box = QVBoxLayout(host)
    field = ClockField(QTime(9, 0), host)
    field.setObjectName("loneTime")
    field.setFixedWidth(180)
    other = QLineEdit(host)
    box.addWidget(field)
    box.addWidget(other)
    host.resize(400, 200)
    _ready(qapp, host)
    _type_over(qapp, field, "nope")
    line = host.findChild(ProblemLine)
    assert line is not None and line.isVisibleTo(host)
    assert line.frameShape() == QFrame.Shape.NoFrame
    assert (line.layout().contentsMargins().left(), line.layout().contentsMargins().right()) == (0, 0)
    assert line.width() == field.width()
    free(host)


def test_a_rows_problem_spans_the_row(qapp: QApplication) -> None:  # noqa: F811
    """Add fixed time's end problem sits under Start and End together (forms.html, grammar on)."""
    parent, _palette = styled(qapp)
    block = shown(qapp, BlockDialog(parent, soccer(), occurrence_day=3))
    _ready(qapp, block)
    _type_over(qapp, block.end, "08:00")
    line = block.findChild(ProblemLine)
    assert line is not None and line.isVisibleTo(block)
    assert line.width() == block._time_row.width()
    assert line.width() > block.end.width()
    free(block)
    free(parent)


def _assert_captions(dialog: QWidget) -> None:
    for field in _inputs(dialog):
        label = _caption_for(field, dialog)
        name = field.objectName() or field.__class__.__name__
        assert label is not None, name
        box = _aligns_with(field)
        assert _bottom(label, dialog) <= _top(box, dialog), (label.text(), name)
        assert _bottom(label, dialog) <= _top(field, dialog), (label.text(), name)
        assert abs(_left(label, dialog) - _left(box, dialog)) <= 8, (label.text(), name)


def test_captions_sit_above_fields_on_every_sheet(qapp: QApplication) -> None:  # noqa: F811
    parent, _palette = styled(qapp)
    opened: list[QDialog] = []
    for dialog in _sheets(parent):
        shown(qapp, dialog)
        opened.append(dialog)
        _assert_captions(dialog)
        if isinstance(dialog, AvailabilityDialog):
            for kind in ("study", "protected"):
                dialog._open_picker(kind=kind, day=0)
                qapp.processEvents()
                _assert_captions(dialog)
                if kind == "protected":
                    assert dialog.picker_title.isVisibleTo(dialog)
                    assert _caption_for(dialog.picker_title, dialog).text() == "Name (optional)"
            dialog._close_picker()
            dialog.tabs.setCurrentIndex(dialog.tabs.findData("cutoff"))
            qapp.processEvents()
            _assert_captions(dialog)
        # More details hides the link, checklist and Spotify fields until it is pressed.
        details = getattr(dialog, "more_details", None)
        if details is not None and not details.isChecked():
            details.setChecked(True)
            qapp.processEvents()
            _assert_captions(dialog)
    host_row = HomeworkRow("2026-10-16")
    host_row.setParent(parent)
    host_row.resize(720, 220)
    host_row.show()
    qapp.processEvents()
    for field in (host_row.name, host_row.minutes, host_row.due):
        label = _caption_for(field, host_row)
        assert label is not None, field.objectName()
        assert _bottom(label, host_row) <= _top(field, host_row)
    activity = ActivityRow("Soccer")
    activity.setParent(parent)
    activity.resize(720, 220)
    activity.show()
    qapp.processEvents()
    for field in (activity.name, activity.category):
        label = _caption_for(field, activity)
        assert label is not None, field.objectName()
        assert _bottom(label, activity) <= _top(field, activity)
    editor = WorkWindowsEditor([{"days": [0], "start": "16:00", "end": "18:00"}])
    editor.setParent(parent)
    editor.resize(640, 240)
    editor.show()
    qapp.processEvents()
    row = editor.findChild(QWidget, "workWindowRow")
    for name in ("workWindowStart", "workWindowEnd", "workWindowSubject"):
        field = row.findChild(QWidget, name)
        label = _caption_for(field, row)
        assert label is not None, name
        assert _bottom(label, row) <= _top(field, row)
        assert abs(_left(label, row) - _left(field, row)) <= 8
    for dialog in opened:
        free(dialog)
    free(parent)


def test_buttons_are_as_wide_as_their_words(qapp: QApplication) -> None:  # noqa: F811
    parent, _palette = styled(qapp)
    opened = []
    for dialog in _sheets(parent):
        shown(qapp, dialog)
        opened.append(dialog)
        for button in dialog.findChildren(QPushButton):
            words = _words(button)
            if not words.strip() or not button.isVisibleTo(dialog) or button.objectName() == "sheetClose":
                continue
            assert button.width() >= button.fontMetrics().horizontalAdvance(words), (words, button.width())
    for dialog in opened:
        free(dialog)
    free(parent)


def test_buttons_stack_when_the_row_is_too_narrow(qapp: QApplication) -> None:  # noqa: F811
    """forms.html stacks the four Delete School answers when the sheet cannot hold them on one line."""
    row = AnswerRow()
    buttons = []
    for words in ("Cancel", "This day only", "This week only", "This week and later"):
        button = QPushButton(words)
        buttons.append(button)
        row.add(button, stretch_before=len(buttons) == 1)
    narrow = 220
    row.resize(narrow, 40)
    row.fit(narrow)
    row.show()
    qapp.processEvents()
    tops = [_top(button, row) for button in buttons]
    assert tops == sorted(tops)
    assert len(set(tops)) == len(buttons)
    for button in buttons:
        assert button.width() >= button.fontMetrics().horizontalAdvance(button.text())
    wide = row.side_by_side() + SHEET_PAD
    row.fit(wide)
    row.resize(wide, 40)
    qapp.processEvents()
    assert len({_top(button, row) for button in buttons}) == 1
    free(row)


def test_account_cards_keep_their_top_when_a_problem_appears(qapp, signed_out) -> None:  # noqa: F811
    window = signed_out
    window.resize(1366, 768)
    pump()
    page = window._stack.currentWidget()
    for mode in ("sign in", "create", "reset"):
        go(window, mode)
        held = card_of(window)
        before = _top(held, page)
        if mode == "create":
            window.username.setText("ab")
            window.password.setText("short")
            window.create_button.click()
        elif mode == "reset":
            window.recover_button.click()
        else:
            window.sign_in_button.click()
        pump()
        assert _top(held, page) == before, mode
        window._clear_auth_problems()
        pump()


def test_account_cards_show_one_problem_and_focus_its_field(qapp, signed_out) -> None:  # noqa: F811
    """forms.html shows the first problem only and moves the keyboard to that field."""
    window = signed_out
    go(window, "create")
    window.username.setText("ab")
    window.password.setText("short")
    window.create_button.click()
    pump()
    visible = [
        line
        for line in (
            window.username_problem,
            window.password_problem,
            window.recovery_code_problem,
            window.recovery_password_problem,
        )
        if line.isVisibleTo(window)
    ]
    assert visible == [window.username_problem]
    assert window.focusWidget() is window.username
    window.username.setText("ada_1")
    window.create_button.click()
    pump()
    visible = [
        line for line in (window.username_problem, window.password_problem) if line.isVisibleTo(window)
    ]
    assert visible == [window.password_problem]
    assert window.focusWidget() is window.password


def test_add_fixed_time_third_step_asks_for_category(qapp: QApplication) -> None:  # noqa: F811
    """The third crumb is Category and the prompt is What category is it? — not How long."""
    parent, _palette = styled(qapp)
    block = shown(qapp, BlockDialog(parent, occurrence_day=3))
    _ready(qapp, block)
    assert [block.findChild(QPushButton, f"blockCrumb{index}").text() for index in range(3)] == [
        "1 What",
        "2 When",
        "3 Category",
    ]
    block.title.setText("Club")
    block._save.click()
    qapp.processEvents()
    block._save.click()
    qapp.processEvents()
    assert block.step_prompt.text() == "What category is it?"
    assert block.category.isVisibleTo(block)
    assert not block.duration_line.isVisibleTo(block)
    free(block)
    free(parent)


def test_captions_sit_above_account_fields(qapp, signed_out) -> None:  # noqa: F811
    window = signed_out
    for mode in ("sign in", "create", "reset"):
        go(window, mode)
        _assert_captions(card_of(window))
