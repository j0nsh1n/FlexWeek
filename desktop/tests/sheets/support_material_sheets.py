"""What the Material 3 sheet and week tests share on the light window: Material on screen, a homework
sheet with a title typed, the week the Edit-homework tests start from, and pointer clicks on QML items.

(`desktop.tests.material_support` has the helpers for finding QML items and putting Material on screen.)"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtCore import QObject, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import CLOCK
from desktop.native.weekmodel import set_clock_24h
from desktop.native.window import NativeWindow
from desktop.tests.material_support import named, pump, show_material
from desktop.tests.window_support import settled

NOW_DAY = 3  # Thursday of the account's week; the clock reads 19:00 on it


def find(root: QObject, name: str) -> QObject:
    found = named(root, name)
    assert found, name
    return found[0]


def centre(item: QObject) -> QPoint:
    spot = item.mapToScene(item.boundingRect().center())
    return QPoint(int(spot.x()), int(spot.y()))


def click(window: NativeWindow, item: QObject, dx: int = 0, dy: int = 0) -> None:
    """A real left click on a QML item through the Quick widget, as the pointer does it."""
    point = centre(item) + QPoint(dx, dy)
    QTest.mouseClick(window._material_page._quick, Qt.MouseButton.LeftButton, pos=point)
    pump(QApplication.instance())


def drag(window: NativeWindow, item: QObject, to: QPoint) -> None:
    quick = window._material_page._quick
    start = centre(item)
    app = QApplication.instance()
    QTest.mousePress(quick, Qt.MouseButton.LeftButton, pos=start)
    pump(app, 4)
    steps = 12
    for step in range(1, steps + 1):
        spot = QPoint(
            start.x() + (to.x() - start.x()) * step // steps,
            start.y() + (to.y() - start.y()) * step // steps,
        )
        QTest.mouseMove(quick, spot)
        pump(app, 2)
    QTest.mouseRelease(quick, Qt.MouseButton.LeftButton, pos=to)
    pump(app, 6)


def open_typed_homework(qapp: QApplication, window: NativeWindow):
    """Material on screen with Add homework open and a title typed. Returns (root, quick widget, sheets)."""
    root = show_material(qapp, window)
    quick = window._material_page._quick
    window.activateWindow()
    quick.setFocus()
    sheets = window._material_page.bridge.sheets
    sheets.openHomework()
    sheets.setText("title", "History essay")
    pump(qapp, 60)
    return root, quick, sheets


def week_monday(window: NativeWindow) -> date:
    return date.fromisoformat(window.session.week_start)


def add_homework(window: NativeWindow, key: str, title: str, minutes: int, due: str) -> None:
    assignment = {"id": key, "title": title, "due": due, "estimate_min": minutes, "revision": 0}
    window.session.add_homework(assignment)
    window.session.save()
    settled(QApplication.instance(), window)


def material_week(qapp: QApplication, window: NativeWindow) -> QObject:
    """Material on the account's week, clock at Thursday 19:00: School Monday to Friday mornings, the
    History essay planned for 18:45 that day, weekends on, 24-hour clock. Returns the QML root."""
    set_clock_24h(True)
    session = window.session
    CLOCK.set(datetime.fromisoformat(session.week_start) + timedelta(days=NOW_DAY, hours=19))
    session.preferences = {**(session.preferences or {}), "show_weekends": True, "clock_24h": True}
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
            "due": (week_monday(window) + timedelta(days=6)).isoformat(),
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
    root = show_material(qapp, window)
    window._material_page.publish()
    pump(qapp)
    return root


def give_the_essay_two_lines(qapp: QApplication, window: NativeWindow) -> None:
    """The essay made 90 minutes long: room for "History" and "essay" on two lines beside the done
    circle, so the circle stays on the title row. At 60 minutes the title has one line, which the circle
    would cut, so the circle hides there (Jonathan, 2026-11-08)."""
    session = window.session
    work = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    work.update({"duration_min": 90})
    session.add_block(work)
    session.save()
    settled(qapp, window)
    pump(qapp)


def block_named(root: QObject, title: str) -> QObject:
    for block in named(root, "weekBlock"):
        if any(str(label.property("text")) == title for label in named(block, "title")):
            return block
    raise AssertionError(f"no block named {title}")


def bridge(window: NativeWindow) -> QObject:
    return window._material_page.bridge


def snack(window: NativeWindow) -> str:
    return str(bridge(window).property("snackText"))
