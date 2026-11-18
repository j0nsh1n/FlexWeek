"""Picture of Material's first setup page: before 1.5.0 step 7 it was the style page, after it is the first
real step (Your week)."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import still


def _first_page(window: NativeWindow) -> object:
    window.resize(1280, 800)
    window.show()
    window._run_setup_again()
    qapp = QApplication.instance()
    wait_until(
        qapp, lambda: window._stack.currentWidget().objectName() == "materialPage", what="Material setup"
    )
    for _ in range(40):
        qapp.processEvents()
    still(window)
    return None


SCREENS: list[Screen] = [
    Screen(
        id="setup.m3_first_page",
        area="setup",
        prepare=_first_page,
        checks="Material's setup opens on its first page with the step rail beside it. No page offers the "
        "Widgets styles or a way to leave Material.",
        sources=("desktop/native/material/qml/setup", "desktop/native/material/bridge_account.py"),
        styles=("material",),
    ),
]
