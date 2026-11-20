"""What the Material 3 screen tests share: putting Material on screen and finding the QML items a
test reads. (Moved out of test_material_window.py so the area folders can import them.)"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.waiting import wait_until

if TYPE_CHECKING:
    from PySide6.QtGui import QImage
    from PySide6.QtQuick import QQuickView, QQuickWindow


def pump(qapp: QApplication, count: int = 30) -> None:
    for _ in range(count):
        qapp.processEvents()


def quick_of(window: NativeWindow) -> QQuickView:
    """The object tests send mouse and key events to; the only place that names the host. Material is its
    own Qt Quick window, so this is the window itself."""
    return window._material_page


def quick_window_of(window: NativeWindow) -> QQuickWindow:
    """The QQuickWindow Material draws in (focus reads go through it): the same object as `quick_of`."""
    return window._material_page


def focus_quick(window: NativeWindow) -> None:
    """Give Material the keyboard."""
    quick_of(window).requestActivate()


def host_has_focus(window: NativeWindow) -> bool:
    """Whether Material's window has the keyboard."""
    return QGuiApplication.focusWindow() is quick_of(window)


def type_text(window: NativeWindow, text: str) -> None:
    """Type `text` into whatever Material has focused, one key at a time (QTest has no keyClicks for a
    Qt Quick window)."""
    for character in text:
        QTest.keyClick(quick_of(window), character)


def grab(window: NativeWindow) -> QImage:
    """An image of what Material drew."""
    return window._material_page.grabWindow()


def page_widget(window: NativeWindow) -> QObject | None:
    """The window on screen (Material's, or the draw-error page), for tests that look inside its children."""
    return window._face()


def page_showing(window: NativeWindow) -> str:
    """The objectName of the window on screen."""
    face = page_widget(window)
    return "" if face is None else str(face.objectName())


def material_showing(window: NativeWindow) -> bool:
    """Seam for step 11: whether Material is the page on screen."""
    return page_showing(window) == "materialPage"


def show_material(qapp: QApplication, window: NativeWindow) -> QObject:
    """Put Material on screen. A refresh must not do this while Settings is open, so leave Settings first."""
    window._surface = "material"
    window._material_gave_up = False
    window._cpu_drawing_version = ""
    window.resize(1280, 800)
    window._on_week()
    pump(qapp)
    grab(window)
    pump(qapp)
    assert material_showing(window)
    root = window._material_page.root
    assert root is not None
    faded_in(qapp, root)
    return root


def faded_in(qapp: QApplication, root: QObject) -> None:
    """Wait for the screen's 300 ms fade-in to end. It runs whenever Material is built or changes
    screen; a test that reads geometry or pixels during it reads them half-faded."""
    stage = qml(root, "materialWeek").parentItem().parentItem()
    wait_until(qapp, lambda: float(stage.property("opacity")) >= 1.0, what="Material to finish fading in")


def qml(root: QObject, name: str) -> QObject:
    found = root.findChild(QObject, name)
    assert found is not None, name
    return found


def visuals(item: QObject) -> list[QObject]:
    """Every painted QML child.

    Repeater.itemAt returns None through PySide, and findChildren misses the rows:
    a delegate's QObject parent is the repeater model, while its visual parent is the grid.
    """
    found: list[QObject] = []
    if not hasattr(item, "childItems"):
        return found
    for child in item.childItems():
        found.append(child)
        found.extend(visuals(child))
    return found


def named(root: QObject, name: str) -> list[QObject]:
    return [item for item in visuals(root) if str(item.objectName()) == name]


def repeater_texts(root: QObject, repeater_name: str, label_name: str) -> list[str]:
    assert root.findChild(QObject, repeater_name) is not None, repeater_name
    return [str(item.property("text")) for item in named(root, label_name)]
