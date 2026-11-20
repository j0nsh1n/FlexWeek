"""The Animations level as the rest of the app sees it. Material's Qt Quick window paces its own
animations and reads the level from `motion_level`; what is left here is Qt's own fades for the menus and
tooltips of the widget windows that remain (the tray menu, dialogs)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from desktop.native.motion_level import EASE_MS, duration, moves, set_app_level


def apply_ui_effects(level: str) -> None:
    """The app's level: Qt's own fades for menus and tooltips, on unless animations are off, its
    sliding dropdown lists only where things may travel, and the level `app_level` gives the rest."""
    set_app_level(level)
    on = duration(EASE_MS) > 0
    for effect in (
        Qt.UIEffect.UI_AnimateMenu,
        Qt.UIEffect.UI_FadeMenu,
        Qt.UIEffect.UI_AnimateTooltip,
        Qt.UIEffect.UI_FadeTooltip,
    ):
        QApplication.setEffectEnabled(effect, on)
    QApplication.setEffectEnabled(Qt.UIEffect.UI_AnimateCombo, moves())
