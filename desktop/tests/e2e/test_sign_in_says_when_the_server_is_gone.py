"""With the real local server stopped, the sign-in card says FlexWeek cannot reach it, not that changes
were lost. (A stopped server is what the light app cannot give: its backend runs inside the test.)"""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QPushButton

from desktop.native.window import NativeWindow
from desktop.server import LocalServer
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import PASSWORD, USERNAME, qapp, server, signed_out, window  # noqa: F401


def test_sign_in_says_when_flexweek_cannot_be_reached(
    qapp: QApplication, window: NativeWindow, server: LocalServer
) -> None:
    window.session.logout()
    wait_until(qapp, lambda: window.session.account is None and not window.session.busy)
    server.stop()
    window.username.setText(USERNAME)
    window.password.setText(PASSWORD)
    window.session._say("")
    window.findChild(QPushButton, "signIn").click()
    wait_until(qapp, lambda: not window.session.busy and bool(window.auth_status.text()))
    assert window.auth_status.text() == (
        "FlexWeek can't reach its server. Close FlexWeek, open it again, then sign in."
    )
    assert window.session.account is None
