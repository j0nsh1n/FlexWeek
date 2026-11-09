"""Month screens for the window chrome: its scroll bar, and the focus ring on Material's date cells (look
checks of test_top_bar and test_pr5b_toast_rings_textsize)."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import CLOCK
from desktop.native.window import NativeWindow
from desktop.tests.material_support import pump as pump_material
from desktop.tests.material_support import show_material, visuals
from desktop.tests.pictures.screen import Screen
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_bar_pictures import WIDGETS_DESIGNS, pump, show_view


def _scrolling_month(window: NativeWindow) -> QObject:
    """August 2026 is six weeks, and a window 520 px high is short enough for those rows to overflow the
    dates, so the bar shows."""
    session = window.session
    CLOCK.set(datetime.fromisoformat("2026-08-13T15:40"))
    session.load_week("2026-08-10")
    wait_until(None, lambda: not session.busy)
    window.resize(1280, 520)
    show_view(window, "month")
    wait_until(None, lambda: session.month_data is not None and window.month_grid.scroll.height() > 0)
    month = window.month_grid.scroll
    month.widget().setMinimumHeight(month.height() * 2)
    pump()
    return month


def _material_date_cell(window: NativeWindow) -> QObject:
    show_material(QApplication.instance(), window)
    window._material_page.bridge.showPage("month")
    pump_material(QApplication.instance(), 10)
    root = window._material_page.root
    cells = [
        item for item in visuals(root) if item.objectName() and item.objectName().startswith("monthDate-")
    ]
    return cells[0] if cells else None


SCREENS: list[Screen] = [
    Screen(
        id="month.scroll_bar",
        area="month",
        prepare=_scrolling_month,
        checks=(
            "Month's scroll bar lies over the right edge of the dates, thin, with no strip kept beside "
            "them; it widens under the pointer as the hours' bar does."
        ),
        sources=("desktop/native/widgets.py", "desktop/native/hours/month.py"),
        styles=WIDGETS_DESIGNS,
    ),
    Screen(
        id="month.date_cell_ring",
        area="month",
        prepare=_material_date_cell,
        checks=(
            "A Material Month date cell's focus ring has a 14 px radius (the card's 12 px plus the 2 px "
            "margin) and is in the theme's primary colour, the same ring the other Material controls use."
        ),
        sources=("desktop/native/material",),
        styles=("material",),
    ),
]
