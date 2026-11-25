"""Pictures of Phone & sync and the centered Phone pairing dialog in Material 3."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen

SOURCES = (
    "desktop/native/material/qml/settings/SyncSection.qml",
    "desktop/native/material/qml/settings/PairingDialog.qml",
    "desktop/native/material/qml/views/SettingsView.qml",
    "desktop/native/material/bridge_settings.py",
    "desktop/native/material/theme.py",
)


def _phone_and_sync(window: NativeWindow) -> object:
    from desktop.tests.sheets.support_material_settings import open_settings

    open_settings(QApplication.instance(), window, "sync")
    return None


def _pairing_dialog(window: NativeWindow) -> object:
    from desktop.tests.settings.support_material_settings import _panel, _pump
    from desktop.tests.sheets.support_material_settings import open_settings

    qapp = QApplication.instance()
    open_settings(qapp, window, "sync")
    panel = _panel(window)
    panel._pair_code = "4829 1037"
    panel._pair_status = "Code works for 4:52. 3 tries left. It works once."
    panel._pair_seconds = 292
    panel._pair_tries = 3
    panel._pair_open = True
    panel._publish()
    _pump(qapp, 20)
    return None


SCREENS: list[Screen] = [
    Screen(
        id="sync.m3_phone_and_sync",
        area="sync",
        prepare=_phone_and_sync,
        checks=(
            "Phone & sync section: status hero card with single colored status word, Linked phones card "
            "with Pair a phone and relay note, and side-by-side Syncs vs Stays local cards."
        ),
        sources=SOURCES,
        main=True,
        styles=("material",),
    ),
    Screen(
        id="sync.m3_pairing_dialog",
        area="sync",
        prepare=_pairing_dialog,
        checks=(
            "Centered pairing dialog pop-up: computer-to-phone graphic header, One-time pairing code "
            "eyebrow, large 4+4 monospace tiles, countdown bar, Copy code, Start a new code, 3 steps, "
            "and n0 relay note."
        ),
        sources=SOURCES,
        main=True,
        styles=("material",),
    ),
]
