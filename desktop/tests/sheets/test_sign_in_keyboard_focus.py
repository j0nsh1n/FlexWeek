"""The sign-in card is measured by laying out its tallest page and going back (`_pin_auth_height`).
Hiding a widget that has focus moves focus off it, so the measuring must leave keyboard focus where
it was. The window is a light one that has signed out, which shows the same sign-in page."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import open_light  # noqa: E402,F401
from desktop.tests.waiting import wait_until  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-sign-in-focus-test"])


@pytest.fixture()
def signed_out(qapp: QApplication, open_light: Callable[..., NativeWindow]) -> NativeWindow:  # noqa: F811
    """The light window after Sign out: the sign-in page, active, with nothing typed."""
    made = open_light()
    made.session.logout()
    wait_until(
        qapp,
        lambda: made._stack.currentWidget().objectName() == "authPage",
        what=lambda: f"the window showed {made._stack.currentWidget().objectName()}",
    )
    made.activateWindow()
    wait_until(qapp, lambda: made.isActiveWindow(), what="the window never became the active one")
    return made


def test_dressing_the_sign_in_page_again_keeps_focus_on_forgot_password(
    qapp: QApplication, signed_out: NativeWindow
) -> None:
    window = signed_out
    forgot = window.findChild(QPushButton, "forgotPassword")
    assert forgot is not None
    forgot.setFocus()
    assert window.focusWidget() is forgot
    window._pin_auth_height()
    assert window.focusWidget() is forgot


def test_dressing_the_reset_page_again_keeps_the_cursor_in_the_recovery_code_box(
    qapp: QApplication, signed_out: NativeWindow
) -> None:
    window = signed_out
    forgot = window.findChild(QPushButton, "forgotPassword")
    assert forgot is not None
    forgot.click()
    window.recovery_code.setFocus()
    assert window.focusWidget() is window.recovery_code
    window._pin_auth_height()
    assert window.focusWidget() is window.recovery_code
