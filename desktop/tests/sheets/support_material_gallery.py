"""The Material 3 component gallery the control tests (and test_pr6b_shapes_buttons_focus.py, through
test_material_components.py) drive: the QML Gallery in a window of its own, and the finders for its
named items."""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import Qt, QUrl
    from PySide6.QtGui import QColor, QGuiApplication
    from PySide6.QtQml import QQmlComponent
    from PySide6.QtQuick import QQuickItem, QQuickView
    from PySide6.QtTest import QTest
    from shiboken6 import delete, isValid

ROOT = Path(__file__).resolve().parents[3]
QML = ROOT / "desktop" / "native" / "material" / "qml"


def _walk(item: QQuickItem) -> Iterator[QQuickItem]:
    yield item
    for child in item.childItems():
        yield from _walk(child)


def _find(item: QQuickItem, name: str) -> QQuickItem:
    for node in _walk(item):
        if node.objectName() == name:
            return node
    raise AssertionError(f"{name} is not in the gallery")


def _child(item: QQuickItem, name: str) -> QQuickItem:
    # The caller keeps `item`. A temporary parent is collected, and shiboken then deletes the child.
    found = item.findChild(QQuickItem, name)
    assert found is not None and isValid(found), name
    return found


def _color(item: QQuickItem, name: str) -> QColor:
    return QColor(_child(item, name).property("color"))


def _press(view: QQuickView, item: QQuickItem, key: Qt.Key) -> None:
    # forceActiveFocus returns None. The key goes to the window only after it is the active focus item.
    view.requestActivate()
    item.forceActiveFocus()
    QGuiApplication.processEvents()
    assert item.hasActiveFocus()
    QTest.keyClick(view, key)
    QGuiApplication.processEvents()


@pytest.fixture(scope="module")
def qapp() -> Iterator[QGuiApplication]:
    yield QGuiApplication.instance() or QGuiApplication(["flexweek-material-components"])


@pytest.fixture
def gallery(qapp: QGuiApplication) -> Iterator[tuple[QQuickView, QQuickItem]]:
    view = QQuickView()
    view.engine().addImportPath(str(QML))
    component = QQmlComponent(view.engine())
    component.setData(b"import components 1.0\nGallery { reduceMotion: true }\n", QUrl())
    assert component.status() == QQmlComponent.Ready, component.errorString()
    root = component.create()
    assert root is not None, component.errorString()
    view.setContent(QUrl(), component, root)
    view.show()
    qapp.processEvents()
    try:
        yield view, root
    finally:
        # The view does not own the gallery item. Closing it leaves both in a cycle, and the suite
        # fails a test that still has a window when the collector runs.
        view.hide()
        view.setSource(QUrl())
        qapp.processEvents()
        if isValid(root):
            delete(root)
        if isValid(view):
            delete(view)
        qapp.processEvents()
