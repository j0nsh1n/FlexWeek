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


def _scrolled(section: str, row: str):
    """The section scrolled to the row named `row` (the objectName a Settings row carries)."""

    def prepare(window: NativeWindow) -> object:
        from desktop.tests.settings.support_material_settings import _flick_to, _named, _pump
        from desktop.tests.sheets.support_material_settings import open_settings

        qapp = QApplication.instance()
        root = open_settings(qapp, window, section)
        _flick_to(_named(root, row)[0])
        _pump(qapp, 10)
        return None

    return prepare


def _focus_custom(window: NativeWindow) -> object:
    from desktop.tests.settings.support_material_settings import _panel, _pump
    from desktop.tests.sheets.support_material_settings import open_settings

    qapp = QApplication.instance()
    open_settings(qapp, window, "focus")
    _panel(window).setTimerPreset("custom")
    _pump(qapp, 20)
    return None


def _preset(name: str):
    def prepare(window: NativeWindow) -> object:
        from desktop.tests.settings.support_material_settings import _panel, _pump
        from desktop.tests.sheets.support_material_settings import open_settings

        qapp = QApplication.instance()
        open_settings(qapp, window, "look")
        _panel(window).setPreset(name)
        _pump(qapp, 20)
        return None

    return prepare


def _preset_screen(name: str) -> Screen:
    slug = name.lower().replace(" ", "_")
    return Screen(
        id=f"settings.m3_preset_{slug}",
        area="settings",
        prepare=_preset(name),
        checks=f"The {name} preset on the Look page: page, cards, text, the selected swatch and the group "
        "titles are readable (text at 4.5 to 1, High contrast at 7 to 1) and the colours are the look's own.",
        sources=SOURCES,
        styles=("material",),
    )


SCREENS: list[Screen] = [
    _screen("alerts", "Alerts shows its settings under plain group titles; each row reads."),
    _screen("focus", "Focus shows the timer choice and its switches under plain group titles."),
    _screen("planning", "Planning shows the planner rows, study hours and school hours under group titles."),
    _screen("look", "Look shows the presets, the accent and the font, with the group titles in primary."),
    Screen(
        id="settings.m3_alerts_all",
        area="settings",
        prepare=_scrolled("alerts", "row_volume"),
        checks="Alerts scrolled to All alerts: volume slider, end chime and keep-running switches.",
        sources=SOURCES,
        styles=("material",),
    ),
    Screen(
        id="settings.m3_planning_hours",
        area="settings",
        prepare=_scrolled("planning", "row_studyHours"),
        checks="Planning scrolled to Study hours: the presets, the hour rows, protected times, Save.",
        sources=SOURCES,
        styles=("material",),
    ),
    Screen(
        id="settings.m3_planning_school",
        area="settings",
        prepare=_scrolled("planning", "row_schoolHours"),
        checks="Planning scrolled to School hours: days, starts, ends, Save.",
        sources=SOURCES,
        styles=("material",),
    ),
    Screen(
        id="settings.m3_focus_custom",
        area="settings",
        prepare=_focus_custom,
        checks="Focus with Custom chosen: a slider for focus, break, long break and long break after.",
        sources=SOURCES,
        styles=("material",),
    ),
    *(_preset_screen(name) for name in ("High contrast", "Paper", "Ink", "Terminal")),
]
