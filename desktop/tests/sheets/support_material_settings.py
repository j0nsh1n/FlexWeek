"""Opening Material 3's Settings and pressing what is on it, as the Settings preview tests (and the Month
tests, through test_material_static_audit.py) do."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.material_support import pump, show_material


def bridge(window: NativeWindow):
    return window._material_page.bridge


def panel(window: NativeWindow):
    return window._material_page.bridge._settings_bridge


def texts(item: QObject) -> list[QObject]:
    found: list[QObject] = []
    for child in item.childItems():
        if child.property("text") is not None and child.property("font") is not None:
            found.append(child)
        found.extend(texts(child))
    return found


def flick_to(item: QObject) -> None:
    parent = item.parentItem()
    while parent is not None:
        if parent.property("contentY") is not None and parent.property("contentHeight") is not None:
            content = parent.property("contentItem")
            spot = item.mapToItem(content, QPointF(0, 0))
            room = max(0.0, float(parent.property("contentHeight")) - float(parent.height()))
            parent.setProperty("contentY", max(0.0, min(room, spot.y() - 60.0)))
            return
        parent = parent.parentItem()


def click(qapp: QApplication, window: NativeWindow, item: QObject) -> None:
    flick_to(item)
    pump(qapp, 5)
    centre = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    quick = window._material_page._quick
    QTest.mouseClick(
        quick,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(int(centre.x()), int(centre.y())),
    )
    pump(qapp, 10)


def click_segment(qapp: QApplication, window: NativeWindow, seg: QObject, label: str) -> None:
    for item in texts(seg):
        if str(item.property("text")) == label:
            click(qapp, window, item)
            return
    raise AssertionError(f"no segment {label!r}")


def open_settings(qapp: QApplication, window: NativeWindow, section: str = "look") -> QObject:
    window.activateWindow()
    window.raise_()
    root = show_material(qapp, window)
    quick = getattr(getattr(window, "_material_page", None), "_quick", None)
    if quick is not None:
        quick.setFocus()
    bridge(window).showPage("settings")
    panel(window).closeAdvanced()
    panel(window).setSection(section)
    pump(qapp)
    return root
