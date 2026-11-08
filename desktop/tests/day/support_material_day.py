"""What the Material Day and My day tests share: an account seeded with a Thursday, and the ways a
test drives the Quick page the way a student does (a click, a wheel turn, a stored look)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from PySide6.QtCore import QObject, QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import CLOCK
from desktop.native.calendar import sunday_due
from desktop.native.weekmodel import set_clock_24h
from desktop.native.window import NativeWindow
from desktop.tests.material_support import named, pump, qml, show_material
from desktop.tests.window_support import look_file, settled

NOW_DAY = 3


def seed_thursday(
    qapp: QApplication, window: NativeWindow, *, hour: int, minute: int = 0, soccer: bool = False
) -> NativeWindow:
    """School 08:00-14:30 Monday to Friday and a History essay planned for 18:45 on Thursday (and,
    with `soccer`, Soccer 16:00-17:30 that day), with the clock held on Thursday at `hour:minute`."""
    session = window.session
    window.home_week = session.week_start
    thursday = datetime.fromisoformat(session.week_start) + timedelta(days=NOW_DAY)
    CLOCK.set(thursday + timedelta(hours=hour, minutes=minute))
    session.selected_day = thursday.date().isoformat()
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
    if soccer:
        session.add_block(
            {
                "id": "soccer",
                "title": "Soccer",
                "kind": "locked",
                "category": "exercise",
                "start": "16:00",
                "duration_min": 90,
                "days": [NOW_DAY],
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
    work.update({"start": "18:45", "days": [NOW_DAY], "duration_min": 60})
    session.add_block(work)
    session.save()
    settled(qapp, window)
    return window


def pref(window: NativeWindow, **values: object) -> None:
    window.session.preferences = {**(window.session.preferences or {}), **values}


def look(window: NativeWindow, **material: str) -> None:
    """Write the Material look the way the look file keeps it, and publish it."""
    path = look_file()
    stored = json.loads(path.read_text()) if path.exists() else {}
    stored["material"] = {**stored.get("material", {}), **material}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(stored))
    window._material_page.publish()
    pump(QApplication.instance())


def bridge_of(window: NativeWindow) -> object:
    return window._material_page.bridge


def root_bridge(root: QObject) -> QObject:
    bridge = root.property("bridge")
    assert bridge is not None
    return bridge


def rows_of(model: QObject) -> list[dict]:
    """Every row of a Rows model as a dict, read the way a QML delegate reads it."""
    names = {int(role): bytes(name).decode() for role, name in model.roleNames().items()}
    found = []
    for at in range(model.rowCount()):
        index = model.index(at, 0)
        found.append({name: model.data(index, role) for role, name in names.items()})
    return found


def centre(item: QObject) -> QPoint:
    spot = item.mapToScene(item.boundingRect().center())
    return QPoint(int(spot.x()), int(spot.y()))


def click(window: NativeWindow, item: QObject) -> None:
    """A real left click on a QML item through the Quick widget, as the pointer does it."""
    quick = window._material_page._quick
    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, pos=centre(item))
    pump(QApplication.instance())


def wheel(quick: QObject, at: QPointF, notches: float, ctrl: bool = True) -> None:
    modifiers = Qt.KeyboardModifier.ControlModifier if ctrl else Qt.KeyboardModifier.NoModifier
    event = QWheelEvent(
        at,
        QPointF(quick.mapToGlobal(at.toPoint())),
        QPoint(),
        QPoint(0, round(120 * notches)),
        Qt.MouseButton.NoButton,
        modifiers,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(quick, event)


def open_day_page(qapp: QApplication, window: NativeWindow, *, weekends: bool = True) -> QObject:
    """Material on its Day page, opened as the student opens it, on the seeded Thursday."""
    set_clock_24h(True)
    pref(window, show_weekends=weekends, clock_24h=True)
    root = show_material(qapp, window)
    sheets = getattr(window._material_page.bridge, "sheets", None)
    if sheets is not None:
        sheets.forceClose()
    window._material_page.publish()
    pump(qapp)
    bridge = bridge_of(window)
    bridge.showPage("day")
    pump(qapp)
    settled(qapp, window)
    pump(qapp)
    # showPage("day") does nothing when Day is already showing. Previous then Next is a new date
    # each time, so the opening scroll runs as it does after the student's own Previous and Next.
    day_bridge = bridge.property("day")
    day_bridge.previousDay()
    settled(qapp, window)
    pump(qapp)
    day_bridge.nextDay()
    settled(qapp, window)
    pump(qapp)
    return root


def day_item(root: QObject) -> QObject:
    return qml(root, "materialDay")


def blocks_by_title(node: QObject) -> dict[str, QObject]:
    found: dict[str, QObject] = {}
    for block in named(node, "weekBlock"):
        title = str(block.property("title") or "")
        if not title:
            titles = [str(label.property("text")) for label in named(block, "title")]
            title = titles[0] if titles else ""
        if title:
            found[title] = block
    return found


def block_named(node: QObject, title: str) -> QObject:
    found = blocks_by_title(node)
    assert title in found, f"no block named {title}"
    return found[title]


def scroll_block_into_view(qapp: QApplication, day: QObject, block: QObject) -> None:
    scroller = qml(day, "dayScroller")
    scroller.setProperty("contentY", max(0.0, float(block.property("y")) - 16.0))
    pump(qapp)
