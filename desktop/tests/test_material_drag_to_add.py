"""Material Week: press-and-drag across empty time opens Add homework with that day and time range."""

from __future__ import annotations

import os
import time
from datetime import timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

pytest_plugins = ["desktop.tests.test_material_week"]

from PySide6.QtCore import QObject, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QWheelEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.test_layouts_window import settled, wait_until  # noqa: E402
from desktop.tests.test_material_week import (  # noqa: E402
    _block_named,
    _bridge,
    _centre,
    _drag,
    _homework,
    _named,
    _pump,
    _qml,
    _week_monday,
)
from desktop.tests.test_material_week import (  # noqa: E402
    _reset as _week_reset,
)


def _reset(window: NativeWindow, qapp: QApplication) -> QObject:
    root = _week_reset(window, qapp)
    sheets = window._material_page.bridge.sheets
    sheets.forceClose()
    sheets.closeMore()
    sheets.dismissNotice()
    settled(qapp, window)
    _pump(qapp)
    return root


def _settle(qapp: QApplication, window: NativeWindow) -> None:
    wait_until(qapp, lambda: not window.session.busy and not window.session.dirty)


def _drag_pos(window: NativeWindow, start: QPoint, to: QPoint) -> None:
    quick = window._material_page._quick
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


def _grid_geometry(root: QObject, window: NativeWindow) -> tuple[QObject, int, int, float, int]:
    grid = _qml(root, "weekScroller")
    hours_item = next(child for child in grid.childItems()[0].childItems() if child.property("width"))
    row = int(_bridge(window).property("hourRow"))
    gutter = int(_qml(root, "materialWeek").property("gutter"))
    day_width = float(_qml(root, "materialWeek").property("dayWidth"))
    saturday = 5
    return hours_item, row, gutter, day_width, saturday


def test_a_drag_across_empty_saturday_9_to_12_opens_add_with_saturday_9_to_12(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    hours_item, row, gutter, day_width, saturday = _grid_geometry(root, window)
    grid = _qml(root, "weekScroller")
    grid.setProperty("contentY", 0.0)
    _pump(qapp)

    p1 = hours_item.mapToScene(QPointF(gutter + saturday * day_width + day_width / 2, 9 * row))
    p2 = hours_item.mapToScene(QPointF(gutter + saturday * day_width + day_width / 2, 12 * row))
    _drag_pos(window, QPoint(int(p1.x()), int(p1.y())), QPoint(int(p2.x()), int(p2.y())))

    sheets = window._material_page.bridge.sheets
    assert sheets.kind == "homework"
    form = sheets.form
    assert form["heading"] == "Add homework"
    assert form["when"] == "fixed"
    assert form["whenDay"] == saturday
    assert form["whenTime"] == "09:00"
    assert form["estimate"] == "180"


def test_dragging_upwards_gives_the_same_range(qapp: QApplication, window: NativeWindow) -> None:
    root = _reset(window, qapp)
    hours_item, row, gutter, day_width, saturday = _grid_geometry(root, window)
    grid = _qml(root, "weekScroller")
    grid.setProperty("contentY", 0.0)
    _pump(qapp)

    p1 = hours_item.mapToScene(QPointF(gutter + saturday * day_width + day_width / 2, 9 * row))
    p2 = hours_item.mapToScene(QPointF(gutter + saturday * day_width + day_width / 2, 12 * row))
    _drag_pos(window, QPoint(int(p2.x()), int(p2.y())), QPoint(int(p1.x()), int(p1.y())))

    sheets = window._material_page.bridge.sheets
    assert sheets.kind == "homework"
    form = sheets.form
    assert form["heading"] == "Add homework"
    assert form["when"] == "fixed"
    assert form["whenDay"] == saturday
    assert form["whenTime"] == "09:00"
    assert form["estimate"] == "180"


def test_saving_the_sheet_places_the_homework_at_that_time(qapp: QApplication, window: NativeWindow) -> None:
    root = _reset(window, qapp)
    hours_item, row, gutter, day_width, saturday = _grid_geometry(root, window)
    grid = _qml(root, "weekScroller")
    grid.setProperty("contentY", 0.0)
    _pump(qapp)

    p1 = hours_item.mapToScene(QPointF(gutter + saturday * day_width + day_width / 2, 9 * row))
    p2 = hours_item.mapToScene(QPointF(gutter + saturday * day_width + day_width / 2, 12 * row))
    _drag_pos(window, QPoint(int(p1.x()), int(p1.y())), QPoint(int(p2.x()), int(p2.y())))

    sheets = window._material_page.bridge.sheets
    assert sheets.kind == "homework"
    sheets.setText("title", "Saturday Math")
    sheets.save()
    _settle(qapp, window)
    assert sheets.kind == ""

    placed = [
        b
        for b in window.session.blocks
        if b.get("assignment_id") in window.session.assignments
        and window.session.assignments[b["assignment_id"]]["title"] == "Saturday Math"
    ]
    assert len(placed) == 1
    block = placed[0]
    assert block["days"] == [saturday]
    assert block["start"] == "09:00"
    assert block["duration_min"] == 180


def test_a_drag_shorter_than_a_quarter_hour_opens_nothing(qapp: QApplication, window: NativeWindow) -> None:
    root = _reset(window, qapp)
    hours_item, row, gutter, day_width, saturday = _grid_geometry(root, window)
    grid = _qml(root, "weekScroller")
    grid.setProperty("contentY", 0.0)
    _pump(qapp)
    week = _qml(root, "materialWeek")
    quick = window._material_page._quick
    # Sideways inside the Saturday column: past the drag threshold, but both ends snap to 09:00.
    start = hours_item.mapToScene(QPointF(gutter + saturday * day_width + 8, 9 * row + 2)).toPoint()
    QTest.mousePress(quick, Qt.MouseButton.LeftButton, pos=start)
    _pump(qapp, 4)
    seen_active = False
    for step in range(1, 13):
        QTest.mouseMove(quick, start + QPoint(step * 3, 0))
        _pump(qapp, 2)
        seen_active = seen_active or bool(week.property("dragRangeActive"))
    QTest.mouseRelease(quick, Qt.MouseButton.LeftButton, pos=start + QPoint(36, 0))
    _pump(qapp, 6)

    assert seen_active, "the drag never started, so this test would prove nothing"
    assert window._material_page.bridge.sheets.kind == ""


def test_a_plain_click_on_empty_time_opens_nothing(qapp: QApplication, window: NativeWindow) -> None:
    root = _reset(window, qapp)
    hours_item, row, gutter, day_width, saturday = _grid_geometry(root, window)
    grid = _qml(root, "weekScroller")
    grid.setProperty("contentY", 0.0)
    _pump(qapp)

    p1 = hours_item.mapToScene(QPointF(gutter + saturday * day_width + day_width / 2, 9 * row))
    quick = window._material_page._quick
    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, pos=QPoint(int(p1.x()), int(p1.y())))
    _pump(qapp, 4)

    sheets = window._material_page.bridge.sheets
    assert sheets.kind == ""


def test_dragging_an_existing_block_or_card_does_not_open_add(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    hours_item, row, gutter, day_width, saturday = _grid_geometry(root, window)
    grid = _qml(root, "weekScroller")
    grid.setProperty("contentY", float(14 * row - 100))
    _pump(qapp)

    # 1. Drag an existing block on the grid
    essay_block = _block_named(root, "History essay")
    essay_block.forceActiveFocus()
    _pump(qapp)
    start_pt = _centre(root, essay_block)
    _drag_pos(window, start_pt, start_pt + QPoint(0, 100))
    _pump(qapp, 4)
    sheets = window._material_page.bridge.sheets
    assert sheets.kind == ""
    # The rejected creation drag leaves the block its keyboard focus, so Enter still opens it.
    assert essay_block.property("activeFocus") is True
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Return)
    _pump(qapp, 6)
    assert sheets.kind == "homework"
    sheets.forceClose()
    _pump(qapp, 4)

    # 2. Drag a card from the drawer onto the grid
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, "drawer_card", "Biology report", 60, due)
    _settle(qapp, window)
    _pump(qapp, 4)
    card = _named(root, "homeworkCard")[0]
    sat_14 = hours_item.mapToScene(QPointF(gutter + saturday * day_width + day_width / 2, 14 * row + 10))
    _drag(window, card, QPoint(int(sat_14.x()), int(sat_14.y())))
    _settle(qapp, window)

    assert sheets.kind == ""
    placed = next((b for b in window.session.blocks if b.get("assignment_id") == "drawer_card"), None)
    assert placed is not None
    assert placed["start"] == "14:00"
    assert placed["days"] == [saturday]


def test_escape_during_a_drag_cancels_it(qapp: QApplication, window: NativeWindow) -> None:
    root = _reset(window, qapp)
    hours_item, row, gutter, day_width, saturday = _grid_geometry(root, window)
    grid = _qml(root, "weekScroller")
    grid.setProperty("contentY", 0.0)
    _pump(qapp)

    p1 = hours_item.mapToScene(QPointF(gutter + saturday * day_width + day_width / 2, 9 * row))
    p2 = hours_item.mapToScene(QPointF(gutter + saturday * day_width + day_width / 2, 12 * row))
    start = QPoint(int(p1.x()), int(p1.y()))
    to = QPoint(int(p2.x()), int(p2.y()))

    quick = window._material_page._quick
    app = QApplication.instance()
    QTest.mousePress(quick, Qt.MouseButton.LeftButton, pos=start)
    _pump(app, 4)
    try:
        for step in range(1, 7):
            spot = QPoint(
                start.x() + (to.x() - start.x()) * step // 12,
                start.y() + (to.y() - start.y()) * step // 12,
            )
            QTest.mouseMove(quick, spot)
            _pump(app, 2)

        week = _qml(root, "materialWeek")
        assert week.property("dragRangeActive") is True
        ghost = _named(root, "rangeGhost")[0]
        assert ghost.property("visible") is True

        QTest.keyClick(window, Qt.Key.Key_Escape)
        _pump(app, 2)

        assert week.property("dragRangeActive") is False
        assert ghost.property("visible") is False
    finally:
        QTest.mouseRelease(quick, Qt.MouseButton.LeftButton, pos=to)
        _pump(app, 6)

    sheets = window._material_page.bridge.sheets
    assert sheets.kind == ""


def test_the_mouse_wheel_still_scrolls_the_grid(qapp: QApplication, window: NativeWindow) -> None:
    root = _reset(window, qapp)
    grid = _qml(root, "weekScroller")
    grid.setProperty("contentY", 100.0)
    _pump(qapp, 4)
    initial_y = float(grid.property("contentY"))

    quick = window._material_page._quick
    win = quick.quickWindow()
    centre = QPointF(quick.width() / 2, quick.height() / 2)
    event = QWheelEvent(
        centre,
        win.mapToGlobal(centre),
        QPoint(0, 0),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QGuiApplication.sendEvent(win, event)
    for _ in range(15):
        _pump(qapp, 2)
        time.sleep(0.02)

    new_y = float(grid.property("contentY"))
    assert new_y != initial_y
