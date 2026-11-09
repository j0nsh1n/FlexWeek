"""Material Settings pages scroll with the mouse wheel when their rows are taller than the window, so a row
below the first screen (everything under "24-hour time" on Look) can be reached."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QGuiApplication, QWheelEvent
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.settings.support_material_settings import _open_settings, _qml
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_the_look_page_scrolls_with_the_wheel_below_the_first_screen(
    qapp: QApplication, window: NativeWindow
) -> None:
    window.resize(1000, 480)
    root = _open_settings(qapp, window, "look")
    page = _qml(root, "lookSection")
    assert float(page.property("contentHeight")) > float(page.height()) + 1, "Look is taller than the window"
    assert float(page.property("contentY")) == 0.0
    win = window._material_page._quick.quickWindow()
    at = page.mapToScene(QPointF(page.width() / 2, page.height() / 2))
    event = QWheelEvent(
        at,
        win.mapToGlobal(at),
        QPoint(0, 0),
        QPoint(0, -240),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QGuiApplication.sendEvent(win, event)
    wait_until(
        qapp,
        lambda: float(page.property("contentY")) > 0.0,
        what=lambda: f"the Look page scrolling; it is at {page.property('contentY')}",
    )
