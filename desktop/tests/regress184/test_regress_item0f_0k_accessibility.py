"""Regression for fix-specs.md items 0f-0k (Accessibility Tester items 2-7), each with the spec's guard.

0f field names (buddy labels), 0g Create-account errors on the field and announced, 0h Tab leaves Notes,
0i Setup's Tab order follows the screen, 0j focus after removing an activity, 0k a readable week list.
Keys go through the window system's path (QTest on the window's QWindow). Accessibility events are not
recorded here (0g's "one alert was sent" needs QAccessible.installUpdateHandler, which PySide does not
expose), so 0g checks focus, description and placement only. Known failures are xfail(strict=True).
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtGui import QAccessible
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QWidget,
)

from desktop.native.weekmodel import clock_text
from desktop.native.widgets import BlockDialog, HomeworkDialog, Segmented
from desktop.tests.regress184.test_regress_item0_time_boxes import _up
from desktop.tests.window_support import free, qapp, server, settled, signed_out, window  # noqa: F401


def press(widget: QWidget, key, mods=Qt.KeyboardModifier.NoModifier) -> None:
    QTest.keyClick(widget.window().windowHandle(), key, mods)
    QApplication.processEvents()


def a11y_name(widget: QWidget) -> str:
    face = QAccessible.queryAccessibleInterface(widget)
    return face.text(QAccessible.Text.Name) if face is not None else ""


@pytest.fixture()
def made(qapp):
    owned: list[QWidget] = []
    yield owned
    for widget in owned:
        widget.hide()
        free(widget)


# 0f ---------------------------------------------------------------------------------------------

KNOWN_0F = (
    "known failure (item 0f; 0.19.0: combos with no buddy read by their value: homeworkPriority, "
    "homeworkEnergy, blockCategory, setupCutoff, ...; Coder's 0f-R names only setupActivityCategory)"
)


def fields_of(root: QWidget) -> list[QWidget]:
    out: list[QWidget] = []
    for widget in root.findChildren(QWidget):
        if not widget.isVisible():
            continue
        if isinstance(widget, QLineEdit) and isinstance(widget.parentWidget(), (QAbstractSpinBox, QComboBox)):
            continue  # the inside of a spin box or combo box, named through its owner
        if isinstance(widget, (QLineEdit, QPlainTextEdit, QComboBox, QAbstractSpinBox, Segmented)):
            out.append(widget)
    return out


def unnamed(root: QWidget) -> list[str]:
    bad = []
    buddies = {label.buddy() for label in root.findChildren(QLabel) if label.buddy() is not None}
    for field in fields_of(root):
        name = a11y_name(field).strip()
        value = field.currentText() if isinstance(field, (QComboBox, Segmented)) else ""
        if isinstance(field, QLineEdit):
            value = field.text()
        placeholder = getattr(field, "placeholderText", lambda: "")()
        label = f"{type(field).__name__}:{field.objectName()}"
        if not name or name in (value, placeholder):
            bad.append(f"{label} named {name!r}")
        if isinstance(field, QComboBox) and field not in buddies:
            bad.append(f"{label} has no buddy label")
    return bad


def open_add_homework(qapp, made) -> QWidget:
    host = QWidget()
    made.append(host)
    dialog = HomeworkDialog(host, today="2026-10-05", category="assignments")
    made.insert(0, dialog)
    _up(qapp, dialog)
    dialog.more_details.setChecked(True)
    qapp.processEvents()
    return dialog


def open_block_editor(qapp, made) -> QWidget:
    host = QWidget()
    made.append(host)
    dialog = BlockDialog(host, day=2, start="16:00", duration_min=60)
    made.insert(0, dialog)
    _up(qapp, dialog)
    qapp.processEvents()
    return dialog


SHEETS = {"add-homework": open_add_homework, "block-editor": open_block_editor}


@pytest.mark.parametrize(
    "sheet",
    [
        pytest.param("add-homework", marks=pytest.mark.xfail(strict=True, reason=KNOWN_0F)),
        # A fixed time no longer asks for a Spotify link, so this sheet's fields are named.
        "block-editor",
    ],
)
def test_0f_every_field_has_a_name_that_is_not_its_value_and_combos_have_a_buddy(qapp, made, sheet) -> None:
    root = SHEETS[sheet](qapp, made)
    assert fields_of(root), "found no fields"
    assert unnamed(root) == []


# 0g ---------------------------------------------------------------------------------------------


# 0h ---------------------------------------------------------------------------------------------

KNOWN_0H = "known failure (item 0h): Notes is a QPlainTextEdit without setTabChangesFocus; Tab types a tab"


@pytest.mark.xfail(strict=True, reason=KNOWN_0H)
def test_0h_tab_leaves_notes_and_shift_tab_comes_back(qapp, made) -> None:
    dialog = open_add_homework(qapp, made)
    notes = dialog.findChild(QPlainTextEdit, "homeworkNotes")
    notes.setFocus(Qt.FocusReason.OtherFocusReason)
    qapp.processEvents()
    press(notes, Qt.Key.Key_Tab)
    assert notes.toPlainText() == "" and QApplication.focusWidget() is not notes
    press(notes, Qt.Key.Key_Backtab, Qt.KeyboardModifier.ShiftModifier)
    assert QApplication.focusWidget() is notes


# 0i / 0j ----------------------------------------------------------------------------------------


# 0k ---------------------------------------------------------------------------------------------

KNOWN_0K = "known failure (item 0k): the week is one painted widget named 'Hours' with no children or list"


@pytest.mark.xfail(strict=True, reason=KNOWN_0K)
def test_0k_a_week_list_names_each_block_with_its_day_and_times(qapp, window) -> None:
    session = window.session
    session.add_block({"id": "school", "title": "School", "kind": "locked", "category": "class",
                       "start": "08:30", "duration_min": 405, "days": [0, 1, 2, 3, 4]})
    session.save()
    settled(qapp, window)
    rows = []
    for listing in window.findChildren(QListWidget):
        if listing.isVisible() or listing.isVisibleTo(window):
            for i in range(listing.count()):
                item = listing.item(i)
                rows.append(f"{item.text()} {item.data(Qt.ItemDataRole.AccessibleTextRole) or ''}")
    school = [r for r in rows if "School" in r]
    # In the user's time format (0.18.5 made new accounts 12-hour; 0.18.4's test assumed 24-hour).
    start, end = clock_text(8 * 60 + 30), clock_text(15 * 60 + 15)
    assert school and any("Mon" in r and start in r and end in r for r in school), rows[:10]


@pytest.mark.xfail(strict=True, reason=KNOWN_0K)
def test_0k_the_grid_is_named_week_view_hours(qapp, window) -> None:
    from desktop.native.hours.canvas import HoursCanvas

    # 0.19.0 shows an empty-week page instead of the grid on a week with nothing in it; give it a block.
    window.session.add_block({"id": "school", "title": "School", "kind": "locked", "category": "class",
                              "start": "08:30", "duration_min": 405, "days": [0, 1, 2, 3, 4]})
    window.session.save()
    settled(qapp, window)
    canvases = [c for c in window.findChildren(HoursCanvas) if c.isVisible()]
    assert canvases and all(c.accessibleName() == "Week view, hours" for c in canvases)
