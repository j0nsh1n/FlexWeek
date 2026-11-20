"""What the hours' zoom, scroll and opening-place tests share: standalone weeks, days and lanes, the
wheel, the light window with school and dinner, and the Material week helpers.

The names `DESIGNS`, `hours`, `qapp`, `wait_until`, `window`, `a_lane_week` and `settle` are imported
by tests of other groups (they came from the old test_hours_open and test_hours_zoom)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import datetime

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import (  # noqa: E402
    QObject,
    QPoint,
    QPointF,
    QStandardPaths,
    Qt,
)
from PySide6.QtGui import QInputDevice, QPointingDevice, QWheelEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QWidget,
)

from backend.tests.fake_clock import CLOCK  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import LightWindows  # noqa: E402
from desktop.tests.material_support import faded_in, grab, material_showing, quick_of  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402, F401

DESIGNS = ("classic",)
MONDAY = "2026-09-21"
SCHOOL = {
    "id": "school",
    "title": "School",
    "kind": "locked",
    "days": [0],
    "start": "08:00",
    "duration_min": 390,
}
ESSAY = {"id": "essay", "title": "Essay", "kind": "locked", "days": [3], "start": "19:00", "duration_min": 90}
NOW = 15 * 60 + 40
# Thursday 15:40 of the week beginning 2026-10-12, so the week the window opens on is not the
# machine's own.
HELD = datetime.fromisoformat("2026-10-15T15:40")

# The hosts of the hands these tests make. A hand is its host's Qt child and holds no reference of
# its own to it, so the host has to be kept for as long as the hand is used.
HOSTS: list = []


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-zoom-test"])


def settle(qapp: QApplication) -> None:
    for _ in range(5):
        qapp.processEvents()


# Standalone hours












def touchpad() -> QPointingDevice:
    """What Qt on Wayland reports a mouse as when the compositor lists one pointer: a touchpad (KDE Plasma,
    2026-11-20). A wheel handler that takes only mice ignores its wheel."""
    return QPointingDevice(
        "wayland pointer",
        9001,
        QInputDevice.DeviceType.TouchPad,
        QPointingDevice.PointerType.Finger,
        QInputDevice.Capability.Position | QInputDevice.Capability.Scroll,
        1,
        0,
    )


def wheel(
    widget: QWidget, at: QPointF, notches: float, ctrl: bool = True, device: QPointingDevice | None = None
) -> None:
    modifiers = Qt.KeyboardModifier.ControlModifier if ctrl else Qt.KeyboardModifier.NoModifier
    extra = () if device is None else (Qt.MouseEventSource.MouseEventNotSynthesized, device)
    event = QWheelEvent(
        at,
        QPointF(widget.mapToGlobal(at.toPoint())),
        QPoint(),
        QPoint(0, round(120 * notches)),
        Qt.MouseButton.NoButton,
        modifiers,
        Qt.ScrollPhase.NoScrollPhase,
        False,
        *extra,
    )
    QApplication.sendEvent(widget, event)








# Lanes








# The light window


@pytest.fixture()
def window(qapp: QApplication, tmp_path_factory: pytest.TempPathFactory, tmp_path) -> Iterator[NativeWindow]:
    """Signed in with the clock held at Thursday 15:40 on 2026-10-15 from before the week is first
    shown: school on weekdays from 08:00, dinner every day at 18:00, and nothing next week."""
    CLOCK.set(HELD)
    windows = LightWindows(qapp, tmp_path_factory.getbasetemp(), tmp_path)
    try:
        made = windows.open((1280, 860))
        session = made.session
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
        session.add_block(
            {
                "id": "dinner",
                "title": "Dinner",
                "kind": "locked",
                "category": "meals",
                "start": "18:00",
                "duration_min": 30,
                "days": [0, 1, 2, 3, 4, 5, 6],
            }
        )
        session.save()
        wait_until(qapp, lambda: not session.busy and not session.dirty)
        yield made
    finally:
        windows.close()








# The Material week


def pump(qapp: QApplication, count: int = 30) -> None:
    for _ in range(count):
        qapp.processEvents()


def show_material(qapp: QApplication, window: NativeWindow) -> QObject:
    """Put Material on screen on the week."""
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


def bridge_of(window: NativeWindow) -> QObject:
    return window._material_page.bridge


def qml(root: QObject, name: str) -> QObject:
    found = root.findChild(QObject, name)
    assert found is not None, name
    return found


def visuals(item: QObject) -> list[QObject]:
    """Every painted QML child. A delegate's QObject parent is the repeater model, while its visual
    parent is the grid, so findChildren misses the rows."""
    found: list[QObject] = []
    if not hasattr(item, "childItems"):
        return found
    for child in item.childItems():
        found.append(child)
        found.extend(visuals(child))
    return found


def named(root: QObject, name: str) -> list[QObject]:
    return [item for item in visuals(root) if str(item.objectName()) == name]


def block_named(root: QObject, title: str) -> QObject:
    for block in named(root, "weekBlock"):
        if any(str(label.property("text")) == title for label in named(block, "title")):
            return block
    raise AssertionError(f"no block named {title}")


def click_item(window: NativeWindow, item: QObject) -> None:
    """A real left click on a QML item through the Quick widget, as the pointer does it."""
    quick = quick_of(window)
    spot = item.mapToScene(item.boundingRect().center())
    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, pos=QPoint(int(spot.x()), int(spot.y())))
    pump(QApplication.instance())


def add_homework(window: NativeWindow, key: str, title: str, minutes: int, due: str) -> None:
    window.session.add_homework(
        {"id": key, "title": title, "due": due, "estimate_min": minutes, "revision": 0}
    )
    window.session.save()
    wait_until(QApplication.instance(), lambda: not window.session.busy and not window.session.dirty)
