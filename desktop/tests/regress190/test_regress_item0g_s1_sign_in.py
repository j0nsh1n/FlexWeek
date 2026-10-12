"""Regression for item 0g's untested flows (fix-specs.md batch 12: Sign in, Reset password, 810 px with
Large text) and QA's S1 (fix-specs-0190.md: the problem line is a row in the layout, the hint hides while
it shows, and re-checks while typing never move focus).

Keys and clicks go through the window system. Known failures are xfail(strict=True).
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QRect, QSignalBlocker, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton, QScrollArea, QWidget

import desktop.native.window as window_module
from desktop.native.client import SIGN_IN_NO_USERNAME, SIGN_IN_SHORT_PASSWORD, USERNAME_ERROR
from desktop.native.fields import ProblemLine
from desktop.tests.window_support import qapp, server, signed_out  # noqa: F401


def up(qapp, w, mode: str) -> None:
    w.resize(1280, 860)
    QTest.qWaitForWindowExposed(w)
    w.activateWindow()
    if mode == "create" and not w.create_button.isVisible():
        w.auth_switch.click()
    elif mode == "reset":
        w.forgot_button.click()
    for _ in range(5):
        qapp.processEvents()


def type_into(qapp, field: QWidget, text: str) -> None:
    field.setFocus(Qt.FocusReason.MouseFocusReason)
    qapp.processEvents()
    for char in text:
        QTest.keyClick(field.window().windowHandle(), char)
    qapp.processEvents()


def quietly(field: QLineEdit, text: str) -> None:
    blocker = QSignalBlocker(field)
    field.setText(text)
    del blocker


def submit(qapp, button: QPushButton) -> None:
    button.setFocus(Qt.FocusReason.TabFocusReason)
    QTest.keyClick(button.window().windowHandle(), Qt.Key.Key_Space)
    for _ in range(5):
        qapp.processEvents()


def shown_problems(w) -> list[ProblemLine]:
    return [line for line in w.findChildren(ProblemLine) if line.isVisible()]


@pytest.fixture()
def alerts(monkeypatch):
    said: list[tuple[str, bool]] = []
    real = window_module.announce

    def spy(widget, words, *, assertive=False):
        said.append((words, assertive))
        return real(widget, words, assertive=assertive)

    monkeypatch.setattr(window_module, "announce", spy)
    return said


def below(w, field: QWidget, line: QWidget) -> int:
    return line.mapTo(w, QPoint(0, 0)).y() - field.mapTo(w, QPoint(0, field.height())).y()


# 0g: Sign in -------------------------------------------------------------------------------------


def test_0g_sign_in_without_a_username_puts_the_message_on_username_and_says_it(
    qapp, signed_out, alerts
) -> None:
    w = signed_out
    up(qapp, w, "sign-in")
    type_into(qapp, w.password, "short")
    submit(qapp, w.sign_in_button)
    assert QApplication.focusWidget() is w.username
    assert w.username.accessibleDescription() == SIGN_IN_NO_USERNAME
    assert alerts == [(f"Error: {SIGN_IN_NO_USERNAME}", True)]
    line = w.username_problem
    assert line.isVisible() and 0 <= below(w, w.username, line) <= 32


def test_0g_sign_in_fix_the_username_and_submit_moves_to_password_then_typing_clears(
    qapp, signed_out
) -> None:
    w = signed_out
    up(qapp, w, "sign-in")
    type_into(qapp, w.password, "short")
    submit(qapp, w.sign_in_button)
    type_into(qapp, w.username, "maya_k")
    submit(qapp, w.sign_in_button)
    assert QApplication.focusWidget() is w.password
    assert w.password.accessibleDescription() == SIGN_IN_SHORT_PASSWORD
    type_into(qapp, w.password, "-long-enough")
    assert shown_problems(w) == [] and w.password.accessibleDescription() == ""


# 0g: Reset password ------------------------------------------------------------------------------


def test_0g_reset_password_walks_username_code_password_with_focus_and_alerts(
    qapp, signed_out, alerts
) -> None:
    w = signed_out
    up(qapp, w, "reset")
    steps = []
    walk = ((w.username, "maya_k"), (w.recovery_code, "ABCD-EFGH"), (w.new_recovery_password, "short"))
    for field, text in walk:
        submit(qapp, w.recover_button)
        steps.append((QApplication.focusWidget() is field, bool(field.accessibleDescription())))
        quietly(field, text)  # typing would hit A18 (S1.6), tested on its own below
    submit(qapp, w.recover_button)
    steps.append((QApplication.focusWidget() is w.new_recovery_password,
                  "more characters" in w.new_recovery_password.accessibleDescription()))
    assert steps == [(True, True)] * 4, steps
    assert len(alerts) == 4 and all(words.startswith("Error: ") and loud for words, loud in alerts), alerts
    type_into(qapp, w.new_recovery_password, "-long-enough")
    assert shown_problems(w) == []


# 0g: 810 px with Large text ----------------------------------------------------------------------


def reachable(w, button: QPushButton) -> bool:
    """On screen in the window, or inside a scroll area that can bring it there."""
    if not button.isVisible():
        return False
    at = QRect(button.mapTo(w, QPoint(0, 0)), button.size())
    if w.rect().contains(at):
        return True
    scroll = button.parentWidget()
    while scroll is not None and not isinstance(scroll, QScrollArea):
        scroll = scroll.parentWidget()
    if scroll is None:
        return False
    scroll.ensureWidgetVisible(button)
    QApplication.processEvents()
    return w.rect().contains(QRect(button.mapTo(w, QPoint(0, 0)), button.size()))


@pytest.mark.parametrize("mode", ["create", "sign-in"])
def test_0g_at_810_px_with_large_text_the_button_stays_reachable_with_a_message(
    qapp, signed_out, mode
) -> None:
    w = signed_out
    up(qapp, w, mode)
    normal = w.username.fontMetrics().height()
    # Signed out, 0.19.0 dresses the card in sanitize_look(None) whatever the device's look (window.py
    # _worn_look), so Large text never reaches it on its own; it is put in Large here to test the layout.
    large = {**window_module.sanitize_look(None), "knobs": {"text": "large"}}
    w._worn_look = lambda: window_module.sanitize_look(large)
    w._apply_appearance()
    w.resize(810, 700)
    for _ in range(5):
        qapp.processEvents()
    w.username.ensurePolished()
    assert w.username.fontMetrics().height() > normal, "Large text not worn"
    button = w.create_button if mode == "create" else w.sign_in_button
    type_into(qapp, w.username, "jo")
    type_into(qapp, w.password, "short")
    submit(qapp, button)
    assert shown_problems(w), "no message shown"
    assert reachable(w, button), f"{button.text()} is out of view at {w.size().toTuple()}"


# S1 ----------------------------------------------------------------------------------------------


def overlaps(w) -> list[str]:
    card = w.username.parentWidget()
    named = ("authError", "keepSignedIn")
    shown = [
        c for c in card.findChildren(QWidget)
        if c.isVisible() and c.parentWidget() is card
        and (isinstance(c, (QLabel, QLineEdit, QPushButton, ProblemLine)) or c.objectName() in named)
    ]
    found = []
    for i, a in enumerate(shown):
        for b in shown[i + 1:]:
            if a.geometry().intersects(b.geometry()):
                found.append(f"{a.objectName() or type(a).__name__} / {b.objectName() or type(b).__name__}")
    return found


def test_s1_create_account_jo_short_then_fixed_no_two_card_rows_overlap(qapp, signed_out) -> None:
    w = signed_out
    up(qapp, w, "create")
    type_into(qapp, w.username, "jo")
    type_into(qapp, w.password, "short")
    seen = []
    submit(qapp, w.create_button)
    seen.append(("jo/short", overlaps(w)))
    type_into(qapp, w.username, "_maya")
    submit(qapp, w.create_button)
    seen.append(("fixed username", overlaps(w)))
    assert all(found == [] for _step, found in seen), seen


def test_s1_the_username_hint_hides_while_its_problem_shows_and_comes_back(qapp, signed_out) -> None:
    w = signed_out
    up(qapp, w, "create")
    type_into(qapp, w.username, "jo")
    submit(qapp, w.create_button)
    assert w.username.accessibleDescription() == USERNAME_ERROR
    assert not w.username_hint.isVisible(), "hint and problem both on screen"
    type_into(qapp, w.username, "_maya")
    assert w.username_hint.isVisible()


@pytest.mark.parametrize("mode", ["create", "reset"])
def test_s1_a18_typing_a_username_after_a_failed_submit_keeps_focus_and_every_key(
    qapp, signed_out, mode
) -> None:
    """Create: no username + short password, submit, then type "maya": at "may" the username is fine, the
    re-check finds the password problem and pulls focus there mid-word. Reset: the first key does it."""
    w = signed_out
    up(qapp, w, mode)
    if mode == "create":
        quietly(w.password, "short")
    submit(qapp, w.create_button if mode == "create" else w.recover_button)
    assert QApplication.focusWidget() is w.username
    for char in "maya":
        QTest.keyClick(w.windowHandle(), char)
    qapp.processEvents()
    got = QApplication.focusWidget()
    assert (got is w.username, w.username.text()) == (True, "maya"), f"focus on {got.objectName()}"


def test_s1_the_problem_line_is_as_wide_as_its_field(qapp, signed_out) -> None:
    w = signed_out
    up(qapp, w, "create")
    type_into(qapp, w.username, "jo")
    submit(qapp, w.create_button)
    assert w.username_problem.width() == w.username.width(), (w.username_problem.width(), w.username.width())


def covered_by_problem(top: QWidget, field: QWidget) -> list[str]:
    from PySide6.QtWidgets import QAbstractButton, QAbstractSpinBox, QComboBox

    lines = [line for line in top.findChildren(ProblemLine) if line.isVisible() and line.field is field]
    assert lines, "no problem line shown"
    area = QRect(lines[0].mapTo(top, QPoint(0, 0)), lines[0].size())
    hit = []
    for other in top.findChildren(QWidget):
        mine = other is field or field.isAncestorOf(other) or lines[0].isAncestorOf(other)
        inner = isinstance(other.parentWidget(), (QAbstractSpinBox, QComboBox))
        control = isinstance(other, (QLineEdit, QAbstractSpinBox, QComboBox, QAbstractButton)) and not inner
        if other.isVisible() and not mine and control and area.intersects(
            QRect(other.mapTo(top, QPoint(0, 0)), other.size())
        ):
            hit.append(other.objectName() or type(other).__name__)
    return hit


def test_s1_block_editor_starts_problem_does_not_cover_end(qapp) -> None:
    """A passing guard on 0.19.0 (S1 acceptance): no control under the line."""
    from desktop.native.widgets import BlockDialog
    from desktop.tests.regress184.test_regress_item0_time_boxes import _up, enter
    from desktop.tests.window_support import free

    dialog = BlockDialog(None, day=1, start="16:00", duration_min=60)
    _up(qapp, dialog)
    try:
        enter(dialog.start, "tab-in")
        for char in "99":
            QTest.keyClick(dialog.windowHandle(), char)
        QTest.keyClick(dialog.windowHandle(), Qt.Key.Key_Tab)
        qapp.processEvents()
        assert covered_by_problem(dialog, dialog.start) == []
    finally:
        QTest.qWait(20)
        dialog.hide()
        free(dialog)


def test_s1_setup_an_unreadable_school_end_pushes_the_activities_down(qapp) -> None:
    """A passing guard on 0.19.0 (S1 acceptance): the line covers no control of the activity section."""
    from desktop.tests.regress184.test_regress_item0_time_boxes import _setup
    from desktop.tests.window_support import free

    box = _setup(qapp, "school-end")
    try:
        box.field.setFocus(Qt.FocusReason.MouseFocusReason)
        box.field.lineEdit().selectAll()
        for char in "99":
            QTest.keyClick(box.top.windowHandle(), char)
        QTest.keyClick(box.top.windowHandle(), Qt.Key.Key_Tab)
        qapp.processEvents()
        assert covered_by_problem(box.top, box.field) == []
    finally:
        QTest.qWait(20)
        for widget in box.owned:
            widget.hide()
            free(widget)
