"""Picking a type in the Add menu opens Add for that type, and saving it puts the block on the week."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_picking_a_type_opens_add_with_that_category(qapp: QApplication, window: NativeWindow) -> None:
    def fill_and_save() -> None:
        dialog = window.findChild(QDialog, "blockDialog")
        # Made before it is shown: accepted then, it would open afterwards and wait for ever.
        if dialog is None or not dialog.isVisible():
            return
        title = dialog.findChild(QLineEdit, "blockTitle")
        title.setText("Soccer practice")
        timer.stop()
        dialog.accept()

    # The top bar once refitted itself on every turn while Add opened (10,000 times a second): a
    # restyle in its own fit asked for the next fit. A handful of fits is what opening Add takes.
    fits = [0]
    fit = window._fit_plan_and_more

    def counted(*args) -> None:
        fits[0] += 1
        fit(*args)

    window._fit_plan_and_more = counted
    timer = QTimer(window)
    timer.setInterval(20)
    timer.timeout.connect(fill_and_save)
    timer.start()
    # The chip strip became the Add menu; picking a type there still opens Add for that type.
    window.add_menu.findChild(QAction, "addMenu-exercise").trigger()
    wait_until(qapp, lambda: any(block["title"] == "Soccer practice" for block in window.session.blocks))
    block = next(item for item in window.session.blocks if item["title"] == "Soccer practice")
    assert block["kind"] == "locked"
    assert block["category"] == "exercise"
    wait_until(qapp, lambda: not window.session.busy)
    assert fits[0] < 100, fits[0]
