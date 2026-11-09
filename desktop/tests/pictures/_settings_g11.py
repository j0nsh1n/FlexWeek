"""Pictures of Material 3 Settings > Look: text contrast on the cards, in light and dark and after
switching modes. (A fragment: the lead gathers these into screens_settings.py.)"""

from __future__ import annotations

from desktop.tests.pictures.screen import Screen

SOURCES = (
    "desktop/native/material/qml/settings",
    "desktop/native/material/bridge_settings.py",
    "desktop/native/material/theme.py",
    "desktop/native/material/tokens.json",
)


def _open_look(window: object) -> object:
    from PySide6.QtWidgets import QApplication

    from desktop.tests.sheets.support_material_settings import open_settings

    open_settings(QApplication.instance(), window, "look")
    return None


def _look_after_mode_switches(window: object) -> object:
    from PySide6.QtWidgets import QApplication

    from desktop.tests.material_support import pump
    from desktop.tests.sheets.support_material_settings import open_settings, panel

    qapp = QApplication.instance()
    open_settings(qapp, window, "look")
    # Light, then Dark, then Light again: the colours of the first light must come back, not stay dark.
    for mode in ("light", "dark", "light"):
        panel(window).setMode(mode)
        pump(qapp, 10)
    return None


SCREENS: list[Screen] = [
    Screen(
        id="settings.material_look_text_contrast",
        area="settings",
        prepare=_open_look,
        checks=(
            "On the Look page the Mode row title, the unselected Mode choice (Dark when Light is selected, "
            "Light otherwise) and the preset names (Blue) each have text contrast of at least 4.5:1 "
            "against their card, in light and in dark."
        ),
        sources=SOURCES,
        main=True,
        styles=("material",),
    ),
    Screen(
        id="settings.material_look_after_mode_switches",
        area="settings",
        prepare=_look_after_mode_switches,
        checks=(
            "After switching Light, then Dark, then Light again, the Look page is drawn in the light "
            "colours with no leftovers of dark: the Mode row title, the unselected choice (Dark) and the "
            "preset names still have text contrast of at least 4.5:1 against the light card."
        ),
        sources=SOURCES,
        styles=("material",),
    ),
]
