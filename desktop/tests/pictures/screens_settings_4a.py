"""Pictures of the Material 3 Settings sections that 1.5.0 step 4a fills in: Alerts, Focus, Planning and
Look, drawn from the top of each page."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen

SOURCES = (
    "desktop/native/material/qml/settings",
    "desktop/native/material/bridge_settings.py",
    "desktop/native/material/theme.py",
    "desktop/native/material/tokens.json",
)


def _section(name: str):
    def prepare(window: NativeWindow) -> object:
        from desktop.tests.sheets.support_material_settings import open_settings

        open_settings(QApplication.instance(), window, name)
        return None

    return prepare


def _screen(section: str, checks: str) -> Screen:
    return Screen(
        id=f"settings.m3_{section}",
        area="settings",
        prepare=_section(section),
        checks=checks,
        sources=SOURCES,
        styles=("material",),
    )


SCREENS: list[Screen] = [
    _screen("alerts", "Alerts shows its settings under plain group titles; every row's title and control are readable."),
    _screen("focus", "Focus shows the timer choice and its switches under plain group titles."),
    _screen("planning", "Planning shows study hours and school hours with the other planner rows under group titles."),
    _screen("look", "Look shows the presets, the accent and the font, with the group titles in primary."),
]
