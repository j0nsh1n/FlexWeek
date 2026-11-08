"""Shared setup for the Week rail, block-word and Material week tests, and for the pictures of them.

Copied verbatim from desktop/tests/test_material_window.py (not owned by this lane): _pump,
_show_material, _qml, _visuals, _named, _repeater_texts. Copied from test_hours_painter.py: Said.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QFont, QFontMetricsF, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from backend.tests.fake_clock import CLOCK
from desktop.native.calendar import sunday_due
from desktop.native.layouts.registry import sanitize_layout
from desktop.native.weekmodel import set_clock_24h
from desktop.native.window import NativeWindow
from desktop.tests.light_app import LightWindows
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import look_file, settled

WIDTH = 1280
# Thursday 19:00 of the week the account opens on.
NOW_DAY = 3
NOW_MINUTE = 19 * 60


class Said(QPainter):
    """A painter that keeps every word it writes, where, and the ink it covers, in the widget's
    coordinates. Put in place of the canvas module's QPainter, it is the one a real paint event
    draws with."""

    words: list[tuple[str, QRectF]] = []
    inks: list[tuple[str, QRectF]] = []
    fonts: list[tuple[str, QFont]] = []

    def drawText(self, *args: object) -> None:  # noqa: N802
        text = next(arg for arg in reversed(args) if isinstance(arg, str))
        where = next(arg for arg in args if isinstance(arg, (QRectF, QRect, QPointF)))
        box = QRectF(where, where) if isinstance(where, QPointF) else QRectF(where)
        flags = next((arg for arg in args if isinstance(arg, (int, Qt.AlignmentFlag))), 0)
        ink = QFontMetricsF(self.font()).boundingRect(box, int(flags), text)
        Said.words.append((text, self.worldTransform().mapRect(box)))
        Said.inks.append((text, self.worldTransform().mapRect(ink)))
        Said.fonts.append((text, QFont(self.font())))
        super().drawText(*args)


# -- the rail (Today's app) -------------------------------------------------


def seeded(qapp: QApplication, window: NativeWindow) -> None:
    """Thursday 15:40: Soccer practice next and Dinner after it, the essay placed at 19:00 and Chem
    on Monday, the worksheet with no time."""
    session = window.session
    thursday = datetime.fromisoformat(session.week_start) + timedelta(days=3, hours=15, minutes=40)
    CLOCK.set(thursday)
    session.add_block(
        {
            "id": "soccer",
            "title": "Soccer practice",
            "kind": "locked",
            "category": "extra",
            "start": "16:00",
            "duration_min": 90,
            "days": [1, 3],
        }
    )
    session.add_block(
        {
            "id": "dinner",
            "title": "Dinner",
            "kind": "locked",
            "category": "meals",
            "start": "18:30",
            "duration_min": 30,
            "days": [3],
        }
    )
    due = sunday_due(session.week_start)
    for key, title in (("essay", "History essay"), ("math", "Math worksheet"), ("chem", "Chem lab report")):
        session.add_homework({"id": key, "title": title, "due": due, "estimate_min": 60, "revision": 0})
    session.save()
    settled(qapp, window)
    for key, day, start in (("essay", 3, "19:00"), ("chem", 0, "20:00")):
        block = next(block for block in session.blocks if block.get("assignment_id") == key)
        session.add_block({**block, "start": start, "days": [day], "pinned": True})
    session.save()
    settled(qapp, window)
    window._layout = sanitize_layout({"main": "classic", "day": "one"})
    window._apply_appearance()
    session.set_view("week")
    window.resize(1280, 860)
    window._on_week()
    pump(qapp)


def pump(qapp: QApplication, count: int = 5) -> None:
    for _ in range(count):
        qapp.processEvents()


def use_clock(qapp: QApplication, window: NativeWindow, twenty_four: bool) -> None:
    """Chooses the clock the way Settings does, so every surface redraws its times."""
    window.session.preferences = {**(window.session.preferences or {}), "clock_24h": twenty_four}
    window._sync_chrome()
    pump(qapp)


def chips(window: NativeWindow) -> list[QPushButton]:
    found = window.rail.findChildren(QPushButton)
    return [chip for chip in found if chip.property("tray") and chip.isVisible()]


# -- the Material week -----------------------------------------------------


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


def _repeater_texts(root: QObject, repeater_name: str, label_name: str) -> list[str]:
    assert root.findChild(QObject, repeater_name) is not None, repeater_name
    return [str(item.property("text")) for item in _named(root, label_name)]


def _pref(window: NativeWindow, **values: object) -> None:
    window.session.preferences = {**(window.session.preferences or {}), **values}


def _look(window: NativeWindow, **material: str) -> None:
    """Write the Material look the way the look file keeps it, and publish it."""
    path = look_file()
    stored = json.loads(path.read_text()) if path.exists() else {}
    stored["material"] = {**stored.get("material", {}), **material}
    path.write_text(json.dumps(stored))
    window._material_page.publish()
    _pump(QApplication.instance())


def seed_material_week(window: NativeWindow, qapp: QApplication) -> NativeWindow:
    """Clock held at Thursday 19:00, School Monday to Friday mornings, the History essay planned for
    18:45 that day, and nothing else placed."""
    session = window.session
    window.home_week = session.week_start
    thursday = datetime.fromisoformat(session.week_start) + timedelta(days=NOW_DAY, hours=19)
    CLOCK.set(thursday)
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
            "due": (date.fromisoformat(session.week_start) + timedelta(days=6)).isoformat(),
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


@pytest.fixture(name="window")
def material_window(
    qapp: QApplication, tmp_path_factory: pytest.TempPathFactory, tmp_path: Path
) -> Iterator[NativeWindow]:
    """The fixture `window`: a fresh light window at 1280 by 800 with the Material week's seed. Each test
    gets its own, so nothing one test placed or toggled reaches the next. A test module imports it as
    `material_window` and asks for `window`."""
    windows = LightWindows(qapp, tmp_path_factory.getbasetemp(), tmp_path)
    try:
        yield seed_material_week(windows.open((WIDTH, 800)), qapp)
    finally:
        windows.close()


def _homework(window: NativeWindow, key: str, title: str, minutes: int, due: str) -> None:
    window.session.add_homework(
        {"id": key, "title": title, "due": due, "estimate_min": minutes, "revision": 0}
    )
    window.session.save()
    settled(QApplication.instance(), window)


def _clean(window: NativeWindow, qapp: QApplication) -> None:
    """Every homework but the essay, and every block but School and the essay, gone."""
    session = window.session
    for key in [item for item in list(session.assignments) if item != "essay"]:
        assert session.delete_homework(key)
        settled(qapp, window)
    extras = [
        block["id"]
        for block in session.blocks
        if block["id"] != "school" and block.get("assignment_id") != "essay"
    ]
    for block_id in extras:
        session.delete_block(block_id)
    essay = session.assignments.get("essay")
    if essay is not None and essay.get("completed"):
        session.complete_homework("essay", False)
    if extras or session.dirty:
        session.save()
    settled(qapp, window)


def _week_monday(window: NativeWindow) -> date:
    return date.fromisoformat(window.session.week_start)


def _centre(root: QObject, item: QObject) -> QPoint:
    spot = item.mapToScene(item.boundingRect().center())
    return QPoint(int(spot.x()), int(spot.y()))


def _click(window: NativeWindow, item: QObject, dx: int = 0, dy: int = 0) -> None:
    """A real left click on a QML item through the Quick widget, as the pointer does it."""
    quick = window._material_page._quick
    point = _centre(window._material_page.root, item) + QPoint(dx, dy)
    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, pos=point)
    _pump(QApplication.instance())


def _drag(window: NativeWindow, item: QObject, to: QPoint) -> None:
    quick = window._material_page._quick
    start = _centre(window._material_page.root, item)
    app = QApplication.instance()
    QTest.mousePress(quick, Qt.MouseButton.LeftButton, pos=start)
    _pump(app, 4)
    steps = 12
    for step in range(1, steps + 1):
        spot = QPoint(
            start.x() + (to.x() - start.x()) * step // steps,
            start.y() + (to.y() - start.y()) * step // steps,
        )
        QTest.mouseMove(quick, spot)
        _pump(app, 2)
    QTest.mouseRelease(quick, Qt.MouseButton.LeftButton, pos=to)
    _pump(app, 6)


def _block_named(root: QObject, title: str) -> QObject:
    for block in _named(root, "weekBlock"):
        if any(str(label.property("text")) == title for label in _named(block, "title")):
            return block
    raise AssertionError(f"no block named {title}")


def _bridge(window: NativeWindow) -> QObject:
    return window._material_page.bridge


def _snack(window: NativeWindow) -> str:
    return str(_bridge(window).property("snackText"))


def _reset(window: NativeWindow, qapp: QApplication) -> QObject:
    """Material on screen on the account's week: standard density, weekends on, clock 24-hour."""
    set_clock_24h(True)
    if window.session.preferences and "dim_completed" in window.session.preferences:
        window.session.preferences.pop("dim_completed", None)
    _pref(window, show_weekends=True, clock_24h=True)
    session = window.session
    home = getattr(window, "home_week", session.week_start)
    if session.week_start != home:
        session.load_week(home)
        settled(qapp, window)
    _clean(window, qapp)
    look_file().unlink(missing_ok=True)
    root = _show_material(qapp, window)
    # A plan that placed everything focuses its snackbar, which holds it open; left over from an
    # earlier test it draws over the grid the pixel tests read.
    bridge = _bridge(window)
    bridge._clear_snack(bridge._snack)
    if hasattr(window._material_page.bridge, "sheets"):
        window._material_page.bridge.sheets.forceClose()
    window._material_page.publish()
    _pump(qapp)
    # Every screen fades in over 300 ms when Material is first built; hand the page back once it has.
    stage = _qml(root, "materialWeek").parentItem().parentItem()
    wait_until(qapp, lambda: float(stage.property("opacity")) >= 1.0, what="Material to finish fading in")
    return root
