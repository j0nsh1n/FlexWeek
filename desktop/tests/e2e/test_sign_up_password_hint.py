"""Creating an account tells the student the password length before they submit, and a short password is
turned away with its reason. Needs the local server and the sign-in page (no account yet), so it runs here
and not on the light app."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from desktop.native.window import NativeWindow
from desktop.tests.window_support import (
    qapp,  # noqa: F401
    server,  # noqa: F401
    signed_out,  # noqa: F401
)


def test_creating_an_account_shows_password_length_before_submit(
    qapp: QApplication, signed_out: NativeWindow
) -> None:
    window = signed_out
    window.findChild(QPushButton, "authSwitch").click()
    qapp.processEvents()
    hint = window.findChild(QLabel, "passwordHint")
    assert hint is not None and hint.isVisible()
    assert "12" in hint.text()
    window.username.setText("newbie")
    window.password.setText("short")
    window.findChild(QPushButton, "createAccount").click()
    qapp.processEvents()
    assert window.session.account is None
    assert window.password_problem.isVisible()
    assert "12" in window.password_problem.text.text()
    assert "password" in window.password_problem.text.text().lower()
