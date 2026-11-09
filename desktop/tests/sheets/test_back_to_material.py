"""The way back to Material from the Widgets styles: a button in Settings and an entry in the More menu."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import pump
from desktop.tests.window_support import qapp, settled  # noqa: F401


def test_back_to_material_button_in_widgets_settings_switches_style(
    qapp: QApplication, window: NativeWindow
) -> None:
    window._use_widgets_styles()
    window._open_settings()
    settled(qapp, window)
    pump(qapp)

    button = window.findChild(QPushButton, "chooseMaterial")
    assert button is not None
    assert button.accessibleName() == "Back to Material"
    assert button.focusPolicy() == Qt.FocusPolicy.StrongFocus

    button.click()
    settled(qapp, window)
    pump(qapp)
    assert window._surface == "material"


def test_back_to_material_in_the_widgets_more_menu(qapp: QApplication, window: NativeWindow) -> None:
    window._use_widgets_styles()
    settled(qapp, window)
    pump(qapp)

    actions = [a for a in window.more_menu.actions() if a.text() == "Back to Material"]
    assert actions, "Back to Material action not found in More menu"
    actions[0].trigger()
    settled(qapp, window)
    pump(qapp)
    assert window._surface == "material"
