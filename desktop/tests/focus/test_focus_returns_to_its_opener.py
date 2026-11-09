"""When Focus mode ends, the keyboard goes back to the control that opened it, or to the hours when that
control is gone. Material and Widgets are held to the same rule."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QStandardPaths, Qt
from PySide6.QtQuick import QQuickItem
from PySide6.QtWidgets import QApplication, QPushButton

from desktop.native.window import NativeWindow
from desktop.tests.day.support_layouts_window import add_school_week
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import pump, qml
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_material_page import fresh_material


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-focus-returns"])


def test_after_focus_mode_ends_focus_returns_to_the_control_that_started_it(
    qapp: QApplication, window: NativeWindow
) -> None:
    # Material
    root = fresh_material(qapp, window)
    bridge = window._material_page.bridge
    scene = window._material_page._quick.quickWindow()

    control = qml(root, "toggleWeekends")
    control.forceActiveFocus()
    pump(qapp)
    assert scene.activeFocusItem() is control

    bridge.focus.show()
    pump(qapp, 5)
    assert bridge.focus.open is True

    bridge.focus.hide()
    pump(qapp, 10)
    assert bridge.focus.open is False
    assert scene.activeFocusItem() is control

    # Widgets
    window._use_widgets_styles()
    button = window.findChild(QPushButton, "addButton")
    button.setFocus(Qt.FocusReason.TabFocusReason)
    pump(qapp)
    assert window.focusWidget() is button

    window._open_focus_screen()
    pump(qapp)
    window._close_focus_screen()
    pump(qapp)
    assert window.focusWidget() is button


def test_focus_mode_return_when_origin_is_deleted_falls_back_without_error(
    qapp: QApplication, window: NativeWindow
) -> None:
    # Material
    root = fresh_material(qapp, window)
    bridge = window._material_page.bridge
    scene = window._material_page._quick.quickWindow()

    origin = QQuickItem(root)
    origin.setObjectName("tempFocusTarget")
    origin.setEnabled(True)
    origin.setVisible(True)
    origin.forceActiveFocus()
    pump(qapp)
    assert scene.activeFocusItem() is origin

    bridge.focus.show()
    pump(qapp, 5)
    assert bridge.focus.open is True

    # The origin is deleted while Focus is open
    origin.deleteLater()
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    pump(qapp, 5)

    # Closing Focus must not raise
    bridge.focus.hide()
    pump(qapp, 10)
    assert bridge.focus.open is False

    # Widgets
    # An empty week shows the empty-week page, which has no hours to return to.
    add_school_week(qapp, window)
    window._use_widgets_styles()
    wait_until(qapp, lambda: bool(window._week_surfaces()), what="the week drawn")
    temporary = QPushButton("Temp Button", window)
    temporary.show()
    temporary.setFocus(Qt.FocusReason.TabFocusReason)
    pump(qapp)
    assert window.focusWidget() is temporary

    window._open_focus_screen()
    pump(qapp)
    temporary.deleteLater()
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    pump(qapp, 5)

    window._close_focus_screen()
    pump(qapp, 5)
    assert window.focusWidget() is window._week_surfaces()[0]
