"""Sign-up and password-reset mistakes are said on the field that has them: focus moves to the field, the
message under it is its accessible description, and a reset error is announced to a screen reader."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.sheets.support_keys import press, up
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


@pytest.fixture()
def signed_out(qapp, window: NativeWindow) -> NativeWindow:
    """The light window after Sign out: the sign-in page, shown and active."""
    window.session.logout()
    wait_until(qapp, lambda: window._stack.currentWidget().objectName() == "authPage")
    return up(qapp, window)


def start_sign_up_with_a_bad_username(qapp, w: NativeWindow) -> None:
    w.findChild(QPushButton, "authSwitch").click()
    qapp.processEvents()
    w.username.setText("jo")
    w.password.setText("short")
    create = w.findChild(QPushButton, "createAccount")
    create.setFocus()
    press(create, Qt.Key.Key_Space)


def test_a_bad_username_moves_focus_to_username_with_the_message_as_its_description(
    qapp, signed_out
) -> None:
    w = signed_out
    start_sign_up_with_a_bad_username(qapp, w)
    wait_until(qapp, lambda: QApplication.focusWidget() is w.username)
    said = w.username.accessibleDescription()
    assert said.startswith("Use 3 to 32")
    shown = [lab for lab in w.findChildren(QLabel) if lab.isVisible() and lab.text() == said]
    assert shown, "the description is not the message on screen"


def test_after_fixing_the_username_focus_stays_there_and_password_has_its_own_message(
    qapp, signed_out
) -> None:
    w = signed_out
    start_sign_up_with_a_bad_username(qapp, w)
    wait_until(qapp, lambda: QApplication.focusWidget() is w.username)
    w.username.setFocus()
    w.username.selectAll()
    QTest.keyClicks(w.username, "good_name")
    qapp.processEvents()
    assert QApplication.focusWidget() is w.username and w.username.text() == "good_name"
    assert "password" in w.password.accessibleDescription().lower()


def test_reset_password_validation_is_announced_under_the_password(qapp, signed_out, monkeypatch) -> None:
    w = signed_out
    announced = []
    monkeypatch.setattr(
        "desktop.native.window.announce",
        lambda field, words, assertive=False: announced.append((field, words, assertive)),
    )
    w.findChild(QPushButton, "forgotPassword").click()
    w.username.setText("student_1")
    w.recovery_code.setText("one-time-code")
    w._recover_account()
    assert QApplication.focusWidget() is w.new_recovery_password
    assert w.new_recovery_password.accessibleDescription() == "Choose a password with at least 12 characters."
    assert w.recovery_password_problem.isVisibleTo(w)
    assert announced == [
        (w.new_recovery_password, "Error: Choose a password with at least 12 characters.", True)
    ]
