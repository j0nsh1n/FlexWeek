"""Week screens for the rail, the Plan and More buttons, the menus and the small-window fits: what
the old week-view tests asserted about sizes and positions, now judged on pictures."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.tests.pictures.screen import Screen

WINDOW = "desktop/native/window.py"
RAIL = "desktop/native/hours/rail.py"
WIDGETS = "desktop/native/widgets.py"


def _app() -> QApplication:
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    return app


















SCREENS: list[Screen] = [
]
