"""Material Week and Day: a click or a drag over empty time opens a menu at that spot, "Add homework
here" and "Add fixed time here", each opening its sheet with that day and time (Jonathan, 2026-11-07)."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from PySide6.QtCore import Q_ARG, Q_RETURN_ARG, QMetaObject, QObject, QPoint, QPointF, Qt
from PySide6.QtGui import QGuiApplication, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import CLOCK
from desktop.native.weekmodel import set_clock_24h
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.material_support import faded_in
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_drag import qapp, settled  # noqa: F401
from desktop.tests.window_support import look_file

# Thursday 19:00 of the week the account opens on.
NOW_DAY = 3


@pytest.fixture()
def window(qapp: QApplication, open_light) -> NativeWindow:  # noqa: F811
    """A fresh window each test, since each one drags and saves: signed in, clock held at Thursday
    19:00, School Monday to Friday mornings and the History essay planned for 18:45 that day."""
    made = open_light((1280, 800))
    wait_until(qapp, lambda: made.session.preferences is not None)
    session = made.session
    CLOCK.set(datetime.fromisoformat(session.week_start) + timedelta(days=NOW_DAY, hours=19))
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
    settled(qapp, made)
    work = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    work.update({"start": "18:45", "days": [NOW_DAY], "duration_min": 60})
    session.add_block(work)
    session.save()
    settled(qapp, made)
    return made


def _pump(qapp: QApplication, count: int = 30) -> None:
    for _ in range(count):
        qapp.processEvents()


def _show_material(qapp: QApplication, window: NativeWindow) -> QObject:
    """Put Material on screen on the account's week."""
    window._surface = "material"
    window._material_gave_up = False
    window._material_failed = ""
    window.resize(1280, 800)
    window._on_week()
    _pump(qapp)
    quick = window._material_page._quick
    quick.grabFramebuffer()
    _pump(qapp)
    assert window._stack.currentWidget().objectName() == "materialPage"
    root = window._material_page.root
    assert root is not None
    faded_in(qapp, root)
    return root


def _visuals(item: QObject) -> list[QObject]:
    """Every painted QML child. Repeater.itemAt returns None through PySide, and findChildren misses
    the rows: a delegate's QObject parent is the repeater model, while its visual parent is the grid."""
    found: list[QObject] = []
    if not hasattr(item, "childItems"):
        return found
    for child in item.childItems():
        found.append(child)
        found.extend(_visuals(child))
    return found


def _named(root: QObject, name: str) -> list[QObject]:
    return [item for item in _visuals(root) if str(item.objectName()) == name]


def _qml(root: QObject, name: str) -> QObject:
    found = root.findChild(QObject, name)
    assert found is not None, name
    return found


def _bridge(window: NativeWindow) -> QObject:
    return window._material_page.bridge


def _homework(window: NativeWindow, key: str, title: str, minutes: int, due: str) -> None:
    window.session.add_homework(
        {"id": key, "title": title, "due": due, "estimate_min": minutes, "revision": 0}
    )
    window.session.save()
    settled(QApplication.instance(), window)


def _week_monday(window: NativeWindow) -> date:
    return date.fromisoformat(window.session.week_start)


def _centre(root: QObject, item: QObject) -> QPoint:
    spot = item.mapToScene(item.boundingRect().center())
    return QPoint(int(spot.x()), int(spot.y()))


def _block_named(root: QObject, title: str) -> QObject:
    for block in _named(root, "weekBlock"):
        if any(str(label.property("text")) == title for label in _named(block, "title")):
            return block
    raise AssertionError(f"no block named {title}")


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


def _reset(window: NativeWindow, qapp: QApplication) -> QObject:
    """Material on screen on the account's week: standard density, weekends on, clock 24-hour, no sheet
    open and no notice showing."""
    set_clock_24h(True)
    session = window.session
    session.preferences = {**(session.preferences or {}), "show_weekends": True, "clock_24h": True}
    look_file().unlink(missing_ok=True)
    root = _show_material(qapp, window)
    bridge = _bridge(window)
    bridge._clear_snack(bridge._snack)
    window._material_page.publish()
    _pump(qapp)
    sheets = bridge.sheets
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


def _slot_menu(root: QObject) -> list[str]:
    """The labels of the open menu over the hours, or nothing when no menu is up."""
    menus = [menu for menu in _named(root, "blockMenu") if menu.property("open")]
    return [entry["label"] for entry in menus[0].property("entries").toVariant()] if menus else []


def _choose(window: NativeWindow, root: QObject, label: str) -> None:
    """Pick a menu entry with the keys, as a student on the keyboard would."""
    labels = _slot_menu(root)
    quick = window._material_page._quick
    for _ in range(labels.index(label)):
        QTest.keyClick(quick, Qt.Key.Key_Down)
    QTest.keyClick(quick, Qt.Key.Key_Return)
    _pump(QApplication.instance(), 4)


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
    assert sheets.kind == ""
    assert _slot_menu(root) == ["Add homework here", "Add fixed time here"]
    _choose(window, root, "Add homework here")
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
    _choose(window, root, "Add homework here")
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
    _choose(window, root, "Add homework here")
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
    assert _slot_menu(root) == []


def _click_at(window: NativeWindow, hours_item: QObject, x: float, y: float) -> None:
    spot = hours_item.mapToScene(QPointF(x, y))
    QTest.mouseClick(
        window._material_page._quick, Qt.MouseButton.LeftButton, pos=QPoint(int(spot.x()), int(spot.y()))
    )
    _pump(QApplication.instance(), 4)


def test_a_click_on_empty_saturday_11_offers_homework_or_fixed_time_and_opens_neither_yet(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    hours_item, row, gutter, day_width, saturday = _grid_geometry(root, window)
    _qml(root, "weekScroller").setProperty("contentY", float(9 * row))
    _pump(qapp)

    _click_at(window, hours_item, gutter + saturday * day_width + day_width / 2, 11 * row + row / 12)

    assert _slot_menu(root) == ["Add homework here", "Add fixed time here"]
    assert window._material_page.bridge.sheets.kind == ""
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Escape)
    _pump(qapp, 4)
    assert _slot_menu(root) == []
    assert window._material_page.bridge.sheets.kind == ""


def test_add_homework_here_from_a_click_opens_add_homework_at_that_day_and_time(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    hours_item, row, gutter, day_width, saturday = _grid_geometry(root, window)
    _qml(root, "weekScroller").setProperty("contentY", float(9 * row))
    _pump(qapp)

    _click_at(window, hours_item, gutter + saturday * day_width + day_width / 2, 11 * row + row / 12)
    _choose(window, root, "Add homework here")

    sheets = window._material_page.bridge.sheets
    assert sheets.kind == "homework"
    form = sheets.form
    assert form["heading"] == "Add homework"
    assert (form["when"], form["whenDay"], form["whenTime"], form["estimate"]) == (
        "fixed",
        saturday,
        "11:00",
        "60",
    )


def test_add_fixed_time_here_from_a_click_opens_add_fixed_time_at_that_day_and_hour(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    hours_item, row, gutter, day_width, saturday = _grid_geometry(root, window)
    _qml(root, "weekScroller").setProperty("contentY", float(9 * row))
    _pump(qapp)

    _click_at(window, hours_item, gutter + saturday * day_width + day_width / 2, 13 * row + row / 12)
    _choose(window, root, "Add fixed time here")

    sheets = window._material_page.bridge.sheets
    assert sheets.kind == "block"
    form = sheets.form
    assert form["heading"] == "Add fixed time"
    assert [day["value"] for day in form["days"] if day["on"]] == [saturday]
    assert (form["start"], form["end"]) == ("13:00", 14 * 60)


def test_add_fixed_time_here_from_a_drag_gets_the_dragged_range(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    hours_item, row, gutter, day_width, saturday = _grid_geometry(root, window)
    _qml(root, "weekScroller").setProperty("contentY", 0.0)
    _pump(qapp)

    p1 = hours_item.mapToScene(QPointF(gutter + saturday * day_width + day_width / 2, 9 * row))
    p2 = hours_item.mapToScene(QPointF(gutter + saturday * day_width + day_width / 2, 12 * row))
    _drag_pos(window, p1.toPoint(), p2.toPoint())
    _choose(window, root, "Add fixed time here")

    sheets = window._material_page.bridge.sheets
    assert sheets.kind == "block"
    form = sheets.form
    assert [day["value"] for day in form["days"] if day["on"]] == [saturday]
    assert (form["start"], form["end"]) == ("09:00", 12 * 60)


def test_a_click_on_a_block_opens_the_block_not_the_add_menu(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    hours_item, row, gutter, day_width, saturday = _grid_geometry(root, window)
    _qml(root, "weekScroller").setProperty("contentY", float(14 * row))
    _pump(qapp)

    _click(window, _block_named(root, "History essay"))

    assert _slot_menu(root) == []
    assert window._material_page.bridge.sheets.kind == "homework"
    assert window._material_page.bridge.sheets.form["heading"] == "Edit homework"


def _empty_time_under(root: QObject, hours_item: QObject, scene: QPointF) -> bool:
    """Whether a window point sits over free time on the week grid, so a click there would reach it."""
    local = hours_item.mapFromScene(scene)
    week = _qml(root, "materialWeek")
    found = QMetaObject.invokeMethod(
        week,
        "emptyGridTimeAt",
        Q_RETURN_ARG("QVariant"),
        Q_ARG("QVariant", float(local.x())),
        Q_ARG("QVariant", float(local.y())),
    )
    return bool(found)


def _open_slot_menu(window: NativeWindow, root: QObject) -> QObject:
    """Click free time on Saturday at 11 and return the grid item the menu was opened from."""
    hours_item, row, gutter, day_width, saturday = _grid_geometry(root, window)
    _qml(root, "weekScroller").setProperty("contentY", float(9 * row))
    _pump(QApplication.instance())
    _click_at(window, hours_item, gutter + saturday * day_width + day_width / 2, 11 * row + row / 12)
    assert _slot_menu(root) == ["Add homework here", "Add fixed time here"]
    return hours_item


def test_undo_on_the_snackbar_over_free_time_opens_no_add_menu(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    hours_item, row, _gutter, _day_width, _saturday = _grid_geometry(root, window)
    _qml(root, "weekScroller").setProperty("contentY", float(14 * row))
    _pump(qapp)
    _click(window, _named(_block_named(root, "History essay"), "weekBlockFinish")[0])
    wait_until(qapp, lambda: str(_bridge(window).property("snackText")) == "Finished History essay.")
    bar = _qml(root, "materialSnackbar")
    undo = bar.mapToScene(QPointF(bar.property("width") - 30, bar.property("height") / 2))
    # Scroll until UNDO sits over free time, where the grid would take a click that fell through.
    for hour in range(24):
        _qml(root, "weekScroller").setProperty("contentY", float(hour * row))
        _pump(qapp)
        if _empty_time_under(root, hours_item, undo):
            break
    assert _empty_time_under(root, hours_item, undo), "no free time under the snackbar"

    QTest.mouseClick(window._material_page._quick, Qt.MouseButton.LeftButton, pos=undo.toPoint())
    _pump(qapp, 4)

    session = window.session
    wait_until(qapp, lambda: not session.busy and not session.assignments["essay"].get("completed"))
    assert _slot_menu(root) == []


def test_a_click_inside_an_open_sheet_over_free_time_opens_no_add_menu(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    hours_item, row, _gutter, _day_width, _saturday = _grid_geometry(root, window)
    _qml(root, "weekScroller").setProperty("contentY", float(9 * row))
    _pump(qapp)
    sheets = window._material_page.bridge.sheets
    sheets.openHomework()
    _pump(qapp, 4)
    card = _qml(root, "sheetCard")
    inside = card.mapToScene(QPointF(card.property("width") - 6, card.property("height") - 6))
    assert _empty_time_under(root, hours_item, inside), "no free time under the sheet"

    QTest.mouseClick(window._material_page._quick, Qt.MouseButton.LeftButton, pos=inside.toPoint())
    _pump(qapp, 4)

    assert _slot_menu(root) == []
    assert sheets.kind == "homework"


def test_a_click_elsewhere_closes_the_add_menu_and_opens_nothing_new(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    hours_item = _open_slot_menu(window, root)
    _hours, row, gutter, day_width, saturday = _grid_geometry(root, window)

    _click_at(window, hours_item, gutter + (saturday - 1) * day_width + day_width / 2, 12 * row + row / 2)

    assert _slot_menu(root) == []
    assert window._material_page.bridge.sheets.kind == ""


def test_escape_on_the_add_menu_gives_the_focus_back_to_the_grid(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    hours_item = _open_slot_menu(window, root)

    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Escape)
    _pump(qapp, 4)

    assert _slot_menu(root) == []
    assert hours_item.property("activeFocus") is True


def test_a_card_that_takes_the_focus_while_the_add_menu_is_open_keeps_it(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, "sheet", "Math worksheet", 30, due)
    _pump(qapp)
    _open_slot_menu(window, root)
    card = _named(root, "homeworkCard")[0]

    card.forceActiveFocus()
    _pump(qapp, 4)

    assert _slot_menu(root) == []
    assert card.property("activeFocus") is True


def test_clicking_a_drawer_card_while_the_add_menu_is_open_opens_the_card_with_the_focus(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, "sheet", "Math worksheet", 30, due)
    _pump(qapp)
    _open_slot_menu(window, root)

    _click(window, _named(root, "homeworkCard")[0])
    _pump(qapp, 6)

    sheets = window._material_page.bridge.sheets
    assert _slot_menu(root) == []
    assert (sheets.kind, sheets.form["heading"]) == ("homework", "Edit homework")
    focused = window._material_page._quick.quickWindow().activeFocusItem()
    assert focused is not None and _qml(root, "sheetCard").isAncestorOf(focused)


def test_a_click_on_empty_time_in_day_offers_the_same_choices_for_that_day(
    qapp: QApplication, window: NativeWindow
) -> None:
    _reset(window, qapp)
    session = window.session
    thursday = (_week_monday(window) + timedelta(days=NOW_DAY)).isoformat()
    session.open_day(thursday)
    settled(qapp, window)
    bridge = window._material_page.bridge
    bridge.showPage("day")
    _pump(qapp, 6)
    try:
        root = window._material_page.root
        scroller = _qml(root, "dayScroller")
        hours_item = scroller.childItems()[0].childItems()[0]
        day_pane = scroller.parentItem()
        gutter = int(day_pane.property("gutter"))
        row = int(day_pane.property("row"))
        scroller.setProperty("contentY", float(16 * row))
        _pump(qapp, 4)

        _click_at(window, hours_item, gutter + 200, 17 * row + row / 12)
        assert _slot_menu(root) == ["Add homework here", "Add fixed time here"]
        _choose(window, root, "Add homework here")

        form = bridge.sheets.form
        assert bridge.sheets.kind == "homework"
        assert (form["whenDay"], form["whenTime"], form["estimate"]) == (NOW_DAY, "17:00", "60")
    finally:
        bridge.sheets.forceClose()
        bridge.showPage("week")
        _pump(qapp, 4)


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
    wait_until(
        qapp,
        lambda: float(grid.property("contentY")) != initial_y,
        what="the wheel moved the grid",
    )
