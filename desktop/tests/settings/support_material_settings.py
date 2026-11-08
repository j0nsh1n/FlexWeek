"""What the Material 3 Settings tests share: putting Material on screen, finding QML items, clicking
them as a pointer does, and opening a section of Settings.

The underscore names are the ones other test files import (test_material_settings.py re-exports them),
so they stay as they were."""

from __future__ import annotations

import json

from PySide6.QtCore import QObject, QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.calendar import sunday_due
from desktop.native.window import NativeWindow
from desktop.tests.window_support import look_file, settled


def _pump(qapp: QApplication, count: int = 30) -> None:
    for _ in range(count):
        qapp.processEvents()


def _show_material(qapp: QApplication, window: NativeWindow) -> QObject:
    """Put Material on screen. A refresh must not do this while Settings is open, so leave Settings first."""
    window._surface = "material"
    window._material_gave_up = False
    window._material_failed = ""
    if window._settings is not None and window._stack.currentWidget() is window._settings:
        window._close_settings(save=False)
    window.resize(1280, 800)
    window._on_week()
    _pump(qapp)
    quick = window._material_page._quick
    quick.grabFramebuffer()
    _pump(qapp)
    assert window._stack.currentWidget().objectName() == "materialPage"
    root = window._material_page.root
    assert root is not None
    return root


def _qml(root: QObject, name: str) -> QObject:
    found = root.findChild(QObject, name)
    assert found is not None, name
    return found


def _visuals(item: QObject) -> list[QObject]:
    """Every painted QML child.

    Repeater.itemAt returns None through PySide, and findChildren misses the rows:
    a delegate's QObject parent is the repeater model, while its visual parent is the grid.
    """
    found: list[QObject] = []
    if not hasattr(item, "childItems"):
        return found
    for child in item.childItems():
        found.append(child)
        found.extend(_visuals(child))
    return found


def _named(root: QObject, name: str) -> list[QObject]:
    return [item for item in _visuals(root) if str(item.objectName()) == name]


def _flick_to(item: QObject) -> None:
    """Scroll the nearest Flickable above `item` so the item is on screen."""
    parent = item.parentItem()
    while parent is not None:
        if parent.property("contentY") is not None and parent.property("contentHeight") is not None:
            content = parent.property("contentItem")
            spot = item.mapToItem(content, QPointF(0, 0))
            room = max(0.0, float(parent.property("contentHeight")) - float(parent.height()))
            parent.setProperty("contentY", max(0.0, min(room, spot.y() - 60.0)))
            return
        parent = parent.parentItem()


def _click(qapp: QApplication, window: NativeWindow, item: QObject) -> None:
    _pump(qapp, 5)
    _flick_to(item)
    _pump(qapp, 5)
    centre = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    quick = window._material_page._quick
    QTest.mouseClick(
        quick,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(int(centre.x()), int(centre.y())),
    )
    _pump(qapp, 10)


def _texts(item: QObject) -> list[QObject]:
    found: list[QObject] = []
    for child in item.childItems():
        if child.property("text") is not None and child.property("font") is not None:
            found.append(child)
        found.extend(_texts(child))
    return found


def _click_segment(qapp: QApplication, window: NativeWindow, seg: QObject, label: str) -> None:
    for item in _texts(seg):
        if str(item.property("text")) == label:
            _click(qapp, window, item)
            return
    raise AssertionError(f"no segment {label!r}")


def _every_quick(item: QObject) -> list[QObject]:
    found: list[QObject] = [item]
    children = item.childItems() if hasattr(item, "childItems") else []
    for child in children:
        found.extend(_every_quick(child))
    return found


def _bridge(window: NativeWindow):
    return window._material_page.bridge


def _panel(window: NativeWindow):
    return window._material_page.bridge._settings_bridge


def _material_file() -> dict:
    """What the look file keeps for Material; nothing when no look has been saved on this computer."""
    if not look_file().exists():
        return {}
    return json.loads(look_file().read_text(encoding="utf-8")).get("material", {})


def _open_settings(qapp: QApplication, window: NativeWindow, section: str = "look") -> QObject:
    root = _show_material(qapp, window)
    _bridge(window).showPage("settings")
    _panel(window).closeAdvanced()
    _panel(window).setSection(section)
    _pump(qapp)
    return root


def _prefs(window: NativeWindow) -> dict:
    return dict(window.session.preferences or {})


def _reset(window: NativeWindow) -> None:
    panel = _panel(window)
    panel.closeAdvanced()
    look_file().unlink(missing_ok=True)
    window._material_page.bridge.reload_material()
    panel.note_applied()
    window._use_widgets_styles()


def school_week_with_an_essay(qapp: QApplication, window: NativeWindow) -> None:
    """School on weekday mornings, a History essay due Sunday and one hour of work on it Thursday at
    18:45: the week the Material window tests were built on. The clock is Thursday 19:00."""
    session = window.session
    session.add_block(
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "category": "class",
            "start": "08:00",
            "duration_min": 390,
            "days": [0, 1, 2, 3, 4],
        }
    )
    session.add_homework(
        {
            "id": "essay",
            "title": "History essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.save()
    settled(qapp, window)
    work = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    work.update({"start": "18:45", "days": [3], "duration_min": 60})
    session.add_block(work)
    session.save()
    settled(qapp, window)
