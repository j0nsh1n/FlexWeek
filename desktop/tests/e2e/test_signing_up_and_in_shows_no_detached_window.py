"""Signing up, out and in again must not show widgets that became windows only while the sign-in
pages were replaced. Needs the local server and a real sign-in, so it runs here and not on the
light app."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton

from desktop.native.window import NativeWindow
from desktop.tests.logic_support import past_setup
from desktop.tests.rig.support_top_level_guard import TopLevelShowGuard, prove_the_guard_sees_a_window
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import (
    PASSWORD,
    USERNAME,
    qapp,  # noqa: F401
    server,  # noqa: F401
    settled,
    signed_out,  # noqa: F401
)


def test_signing_up_out_and_in_never_shows_a_detached_child_as_a_window(
    qapp: QApplication, signed_out: NativeWindow
) -> None:
    window = signed_out
    guard = TopLevelShowGuard(window)
    qapp.installEventFilter(guard)
    try:
        prove_the_guard_sees_a_window(qapp, guard)
        window.username.setText(USERNAME)
        window.password.setText(PASSWORD)
        window.findChild(QPushButton, "createAccount").click()
        wait_until(qapp, lambda: window._stack.currentWidget().objectName() == "recoveryPage")
        window.recovery_ack.setChecked(True)
        window.recovery_continue.click()
        past_setup(qapp, window)
        settled(qapp, window)

        window.session.logout()
        wait_until(qapp, lambda: window._stack.currentWidget().objectName() == "authPage")
        window.username.setText(USERNAME)
        window.password.setText(PASSWORD)
        window.findChild(QPushButton, "signIn").click()
        wait_until(qapp, lambda: window.session.account is not None)
        settled(qapp, window)

        assert guard.unexpected == [], "Unexpected top-level Show events:\n" + "\n".join(guard.unexpected)
    finally:
        qapp.removeEventFilter(guard)
        guard.main = None
        guard.deleteLater()
