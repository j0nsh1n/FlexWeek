"""What the tests of Esc and the keyboard on Settings and its sheets share: opening Material's Settings at
a section, and showing a dialog the way a window shows it."""

from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication, QDialog

from desktop.native.window import NativeWindow
from desktop.tests.material_support import pump, show_material
from desktop.tests.window_support import still


def bridge(window: NativeWindow):
    return window._material_page.bridge


def panel(window: NativeWindow):
    return bridge(window)._settings_bridge


def open_settings(qapp: QApplication, window: NativeWindow, section: str = "look") -> QObject:
    root = show_material(qapp, window)
    bridge(window).showPage("settings")
    panel(window).closeAdvanced()
    panel(window).setSection(section)
    pump(qapp)
    return root


def shown(qapp: QApplication, dialog: QDialog) -> QDialog:
    dialog.show()
    for _ in range(4):
        qapp.processEvents()
    parent = dialog.parentWidget()
    still(dialog, *([parent.window()] if parent is not None else []))
    return dialog
