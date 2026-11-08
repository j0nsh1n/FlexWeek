"""Putting the Material week on a light window with nothing open, for the toast, focus and tab tests."""

from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.material_support import pump, show_material
from desktop.tests.window_support import look_file


def fresh_material(qapp: QApplication, window: NativeWindow) -> QObject:
    """Material on screen at the week, with no sheet, notice or older message left over."""
    look_file().unlink(missing_ok=True)
    root = show_material(qapp, window)
    bridge = window._material_page.bridge
    if hasattr(bridge, "sheets"):
        bridge.sheets.forceClose()
        bridge.sheets.dismissNotice()
    bridge.note("")
    bridge.showPage("week")
    window._material_page.publish()
    pump(qapp, 10)
    return root
