"""The window carries the buttons for quick focus, restore points, the account and More."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from PySide6.QtWidgets import QPushButton

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.window_support import qapp  # noqa: F401


def test_native_window_exposes_focus_restore_and_account_controls(window: NativeWindow) -> None:
    for name in (
        "focusQuick",
        "restoreButton",
        "accountButton",
        "moreButton",
    ):
        assert window.findChild(QPushButton, name) is not None, name
    copy_day = window.findChild(QPushButton, "copyDay")
    assert copy_day is not None
    assert copy_day.parent().objectName() == "moreOverflow"
