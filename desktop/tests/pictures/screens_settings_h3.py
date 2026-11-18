"""Pictures of the Settings pages: where things sit, how wide they are, the colours and contrast of what is
drawn. These were checks in code (test_settings_0183, test_settings_look, test_settings_finding,
test_settings_words, test_material_settings) and are judged on the picture now."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.settings.support_material_settings import _bridge, _panel, _show_material


def _pump(times: int = 20) -> None:
    for _ in range(times):
        QApplication.processEvents()


def _material_cutoff(window: NativeWindow) -> object:
    window.resize(800, 800)
    _show_material(QApplication.instance(), window)
    window.resize(800, 800)
    _bridge(window).showPage("settings")
    _panel(window).closeAdvanced()
    _panel(window).setSection("planning")
    _pump(30)
    return None


def _availability_cutoff(window: NativeWindow) -> object:
    from desktop.native.widgets import AvailabilityDialog

    dialog = AvailabilityDialog(window, {})
    dialog.show()
    dialog.tabs.setCurrentIndex(dialog.tabs.findData("cutoff"))
    _pump(5)
    return dialog


SCREENS: list[Screen] = [
    Screen(
        id="settings.material_planning_cutoff",
        area="settings",
        prepare=_material_cutoff,
        checks=(
            "Material 3 Settings, Planning, in a window 800 px wide (also 860 and 900): the cut-off"
            " segmented control ends inside the page's clipping area (its right edge is no more than half"
            " a pixel past it), so no choice is cut off."
        ),
        sources=("desktop/native/material/",),
    ),
    Screen(
        id="settings.availability_cutoff",
        area="settings",
        prepare=_availability_cutoff,
        checks=(
            "On the Study hours sheet's cut-off tab the label 'No homework after' sits above the cut-off"
            " box and is shown once."
        ),
        sources=("desktop/native/widgets.py",),
    ),
]
