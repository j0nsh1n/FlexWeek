# ruff: noqa: F811
"""What the Material sheet tests share: a light Material window with School and a History essay in
the week, the sheets bridge, and the few QML helpers the sheet tests read with.

The week the fixtures build: School Monday to Friday 08:00 to 14:30, a History essay due Sunday and
planned Thursday 18:45 for an hour, and the one clock at Thursday 19:00.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QStandardPaths, QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlComponent  # noqa: E402
from PySide6.QtQuick import QQuickItem, QQuickView  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from shiboken6 import delete, isValid  # noqa: E402

from desktop.native.calendar import sunday_due  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import open_light  # noqa: E402,F401
from desktop.tests.material_support import named, show_material  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402

QML = Path(__file__).resolve().parents[2] / "native" / "material" / "qml"
DISCARD = "Discard what you typed?"


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-material-sheets"])


def settle(qapp: QApplication, shell: NativeWindow) -> None:
    wait_until(
        qapp,
        lambda: not shell.session.busy and not shell.session.dirty,
        what="the session to finish saving",
    )


def seed_school_and_essay(qapp: QApplication, shell: NativeWindow) -> None:
    session = shell.session
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
    settle(qapp, shell)
    work = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    work.update({"start": "18:45", "days": [3], "duration_min": 60})
    session.add_block(work)
    session.save()
    settle(qapp, shell)


@pytest.fixture()
def shell(qapp: QApplication, open_light: Callable[..., NativeWindow]) -> NativeWindow:
    """A light window at 1280 by 800 with School and the History essay in the week."""
    made = open_light((1280, 800))
    seed_school_and_essay(qapp, made)
    return made


@pytest.fixture()
def sheets(qapp: QApplication, shell: NativeWindow):
    """The Material sheets bridge, with Material on screen."""
    show_material(qapp, shell)
    return shell._material_page.bridge.sheets


def find_named(root: QObject, name: str) -> QObject:
    found = named(root, name)
    assert found, name
    return found[0]


def type_homework(sheets, title: str) -> None:
    sheets.setText("title", title)


# The component gallery: the shared Material controls alone in a view, for what a control does with
# keys and clicks.


def _walk(item: QQuickItem) -> Iterator[QQuickItem]:
    yield item
    for child in item.childItems():
        yield from _walk(child)


def gallery_find(item: QQuickItem, name: str) -> QQuickItem:
    for node in _walk(item):
        if node.objectName() == name:
            return node
    raise AssertionError(f"{name} is not in the gallery")


def gallery_child(item: QQuickItem, name: str) -> QQuickItem:
    # The caller keeps `item`. A temporary parent is collected, and shiboken then deletes the child.
    found = item.findChild(QQuickItem, name)
    assert found is not None and isValid(found), name
    return found


@pytest.fixture()
def gallery(qapp: QGuiApplication) -> Iterator[tuple[QQuickView, QQuickItem]]:
    view = QQuickView()
    view.engine().addImportPath(str(QML))
    component = QQmlComponent(view.engine())
    component.setData(b"import components 1.0\nGallery { reduceMotion: true }\n", QUrl())
    assert component.status() == QQmlComponent.Status.Ready, component.errorString()
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
