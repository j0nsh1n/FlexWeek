"""The sign-up page against the real server: eight recovery codes then an empty week, the password can be
shown, and a short username is named before anything is sent."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton

from desktop.native.client import USERNAME_ERROR
from desktop.native.window import NativeWindow
from desktop.tests.e2e.account_sessions import HASHING_WAIT, table_text
from desktop.tests.logic_support import past_setup
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import PASSWORD, qapp, server, signed_out  # noqa: F401


def test_creating_an_account_shows_eight_codes_then_an_empty_week(
    qapp: QApplication, signed_out: NativeWindow
) -> None:
    window = signed_out
    window.username.setText("alice")
    window.password.setText(PASSWORD)
    window.findChild(QPushButton, "createAccount").click()
    wait_until(qapp, lambda: window._stack.currentWidget().objectName() == "recoveryPage", HASHING_WAIT)
    codes = window.recovery_list.text().splitlines()
    assert len(codes) == 8
    assert all(len(code) >= 8 for code in codes)
    window.recovery_ack.setChecked(True)
    window.recovery_continue.click()
    past_setup(qapp, window)
    assert window.session.blocks == []
    assert window.session.revision == 0
    assert table_text(window) == ""


def test_the_password_can_be_shown(qapp: QApplication, signed_out: NativeWindow) -> None:
    window = signed_out
    window.password.setText(PASSWORD)
    assert window.password.echoMode() == QLineEdit.EchoMode.Password
    window.password_reveal.click()
    assert window.password.echoMode() == QLineEdit.EchoMode.Normal
    assert window.password_reveal.toolTip() == "Hide password"
    window.password_reveal.click()
    assert window.password.echoMode() == QLineEdit.EchoMode.Password
    assert window.password_reveal.toolTip() == "Show password"


def test_a_short_username_is_named_before_the_request(qapp: QApplication, signed_out: NativeWindow) -> None:
    window = signed_out
    window.username.setText("ab")
    window.password.setText(PASSWORD)
    window.findChild(QPushButton, "createAccount").click()
    assert window.session.account is None
    assert window.username_problem.text.text() == USERNAME_ERROR
    assert not window.username_problem.isHidden()
