"""The Undo button in a notice does what it says: a click or Space takes the change back and the
notice closes."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_space_on_the_undo_button_takes_the_change_back_and_closes_the_notice(
    qapp: QApplication, window: NativeWindow
) -> None:
    undone: list[bool] = []
    toast = window.toast
    toast.show_message("Moved block", "Undo", callback=lambda: undone.append(True))
    toast.reposition()
    qapp.processEvents()
    assert toast.isVisible()
    assert toast.button.isVisible()
    assert "Undo" in toast.button.text()

    window.activateWindow()
    wait_until(qapp, window.isActiveWindow)
    toast.button.setFocus()
    wait_until(qapp, toast.button.hasFocus, what="Undo has the keyboard")
    QTest.keyClick(toast.button, Qt.Key.Key_Space)
    qapp.processEvents()

    assert undone == [True]
    assert not toast.isVisible()


def test_clicking_the_undo_button_takes_the_change_back_and_closes_the_notice(
    qapp: QApplication, window: NativeWindow
) -> None:
    undone: list[bool] = []
    toast = window.toast
    toast.show_message("Another move", "Undo", callback=lambda: undone.append(True))
    toast.reposition()
    qapp.processEvents()
    assert toast.isVisible()
    toast.button.click()
    qapp.processEvents()
    assert undone == [True]
    assert not toast.isVisible()
