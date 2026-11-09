"""Keys and focus the way the window system delivers them, for tests of sheets and fields.

Keys go to the widget's QWindow (QTest on `windowHandle()`), the path a real key takes. Sending QTest events
straight at a widget of a window that was never activated loses the first key."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAccessible
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QWidget,
)

from desktop.native.fields import ClockField
from desktop.native.widgets import Segmented

NONE = Qt.KeyboardModifier.NoModifier


def up(qapp: QApplication, widget: QWidget) -> QWidget:
    """Show `widget`, wait until it is on screen and active, so the first key reaches it."""
    widget.show()
    assert QTest.qWaitForWindowExposed(widget)
    widget.activateWindow()
    qapp.processEvents()
    return widget


def press(widget: QWidget, key, mods=NONE) -> None:
    QTest.keyClick(widget.window().windowHandle(), key, mods)
    QApplication.processEvents()


def type_text(widget: QWidget, text: str) -> None:
    for char in text:
        press(widget, char)


def a11y_name(widget: QWidget) -> str:
    face = QAccessible.queryAccessibleInterface(widget)
    return face.text(QAccessible.Text.Name) if face is not None else ""


def hhmm(field: ClockField) -> str:
    minutes = field.minutes()
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def tab_in(field: ClockField) -> None:
    """Get the keyboard into the box with a real Tab from the widget before it in the focus chain."""
    before = field.previousInFocusChain()
    # The chain is a ring: a dialog that was never shown has no visible widget in it, so stop after one lap.
    for _lap in range(len(QApplication.allWidgets()) + 2):
        if (
            before.isVisible()
            and before.isEnabled()
            and before.focusPolicy() & Qt.FocusPolicy.TabFocus
            and before is not field.lineEdit()
        ):
            break
        before = before.previousInFocusChain()
    else:
        raise AssertionError("no visible, tab-focusable widget before the box: is its dialog shown?")
    before.setFocus(Qt.FocusReason.OtherFocusReason)
    QApplication.processEvents()
    press(field, Qt.Key.Key_Tab)
    assert field.hasFocus() or field.lineEdit().hasFocus(), "Tab did not give the box the keyboard"


def tab_into(segmented: Segmented) -> QWidget | None:
    """Focus the widget before the control in the focus chain and press Tab, as a student does."""
    first = segmented.buttons()[0]
    before = first.previousInFocusChain()
    while before is not None and (
        before in segmented.buttons()
        or not (before.isVisible() and before.focusPolicy() & Qt.FocusPolicy.TabFocus)
    ):
        before = before.previousInFocusChain()
    assert before is not None
    before.setFocus(Qt.FocusReason.OtherFocusReason)
    QApplication.processEvents()
    press(before, Qt.Key.Key_Tab)
    return QApplication.focusWidget()


def fields_of(root: QWidget) -> list[QWidget]:
    """The visible entry fields of a sheet or page: line edits, notes, combo and spin boxes, segments."""
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
    """Every field of `root` a screen reader would announce with no name, or with only its own value."""
    bad = []
    buddies = {label.buddy() for label in root.findChildren(QLabel) if label.buddy() is not None}
    for field in fields_of(root):
        label = f"{type(field).__name__}:{field.objectName()}"
        if isinstance(field, QComboBox):
            # Qt answers a combo box's accessible Name with its current text whatever is set, so a screen
            # reader takes its label from the "labelled by" relation that a buddy creates. A name of its own
            # does not stand in for the buddy.
            if field not in buddies:
                bad.append(f"{label} has no buddy label")
            continue
        name = a11y_name(field).strip()
        value = field.currentText() if isinstance(field, Segmented) else ""
        if isinstance(field, QLineEdit):
            value = field.text()
        placeholder = getattr(field, "placeholderText", lambda: "")()
        if not name or name in (value, placeholder):
            bad.append(f"{label} named {name!r}")
    return bad
