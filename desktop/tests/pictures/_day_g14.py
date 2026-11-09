"""Day screens for the window chrome: Timeline day's top bar at Large text, and Material's day rows at larger
text (look checks of test_window_screens and test_pr5b_toast_rings_textsize)."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.layouts.registry import sanitize_layout
from desktop.native.window import NativeWindow
from desktop.tests.material_support import pump as pump_material
from desktop.tests.material_support import show_material
from desktop.tests.pictures.screen import Screen
from desktop.tests.week.support_bar_pictures import idle, pump, text_size


def _timeline_day_at_large_text(window: NativeWindow) -> None:
    text_size(window, "large")
    window._layout = sanitize_layout({"main": "timeline", "day": "one"})
    window._day_mode = True
    window._on_week()
    window.resize(1150, 768)
    idle(window)
    pump(6)
    return None


def _material_day_rows(window: NativeWindow) -> None:
    show_material(QApplication.instance(), window)
    window._material_page.bridge.showPage("day")
    pump_material(QApplication.instance(), 10)
    return None


SCREENS: list[Screen] = [
    Screen(
        id="day.top_bar_timeline_large_text",
        area="day",
        prepare=_timeline_day_at_large_text,
        checks=(
            "At 1150 px with Large text on Timeline's day, the top bar is one row (a wrapped bar ate about "
            "55 px and pushed the Due chips off screen): Plan sits above the foot of the title, Plan reads "
            "Plan my homework, Plan homework or Plan, More reads More or only its icon, and no button on "
            "the bar is cut."
        ),
        sources=(
            "desktop/native/window.py",
            "desktop/native/layouts/timeline.py",
            "desktop/native/widgets.py",
        ),
        styles=("timeline",),
    ),
    Screen(
        id="day.material_larger_text_rows",
        area="day",
        prepare=_material_day_rows,
        checks=(
            "Material's Day at Larger text has rows at least 1.5 times the height they have at Normal text "
            "(56 px), and their text is not clipped."
        ),
        sources=("desktop/native/material",),
        styles=("material",),
    ),
]
