"""Material design: opening homework for editing on click/Enter/Space, finish button, context menus."""

from __future__ import annotations

import os
from datetime import timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

pytest_plugins = ["desktop.tests.test_material_week"]

from PySide6.QtCore import QObject, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QAccessible, QAccessibleInterface  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.logic_support import past_setup  # noqa: E402,F401
from desktop.tests.test_layouts_window import settled, wait_until  # noqa: E402
from desktop.tests.test_material_week import (  # noqa: E402
    _block_named,
    _bridge,
    _centre,
    _click,
    _drag,
    _homework,
    _named,
    _pump,
    _qml,
    _snack,
    _week_monday,
)
from desktop.tests.test_material_week import (  # noqa: E402
    _reset as _week_reset,
)
from desktop.tests.test_material_window import _visuals  # noqa: E402


def _reset(window: NativeWindow, qapp: QApplication) -> QObject:
    if "essay" in window.session.assignments:
        window.session.assignments["essay"]["title"] = "History essay"
    return _week_reset(window, qapp)


def _settle(qapp: QApplication, window: NativeWindow) -> None:
    wait_until(qapp, lambda: not window.session.busy and not window.session.dirty)


def test_clicking_a_homework_block_opens_edit_and_keeps_it_unfinished(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    essay = _block_named(root, "History essay")
    assert window.session.assignments["essay"].get("completed") in (None, False)
    _click(window, essay)
    sheets = window._material_page.bridge.sheets
    wait_until(qapp, lambda: sheets.kind == "homework")
    assert sheets.form["heading"] == "Edit homework"
    assert sheets.form["title"] == "History essay"
    assert window.session.assignments["essay"].get("completed") in (None, False)
    sheets.forceClose()
    _settle(qapp, window)


def test_enter_on_a_focused_block_opens_edit(qapp: QApplication, window: NativeWindow) -> None:
    root = _reset(window, qapp)
    essay = _block_named(root, "History essay")
    essay.forceActiveFocus()
    _pump(qapp)
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Return)
    sheets = window._material_page.bridge.sheets
    wait_until(qapp, lambda: sheets.kind == "homework")
    assert sheets.form["heading"] == "Edit homework"
    assert sheets.form["title"] == "History essay"
    sheets.forceClose()
    _settle(qapp, window)


def test_space_on_a_focused_block_opens_edit(qapp: QApplication, window: NativeWindow) -> None:
    root = _reset(window, qapp)
    essay = _block_named(root, "History essay")
    essay.forceActiveFocus()
    _pump(qapp)
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Space)
    sheets = window._material_page.bridge.sheets
    wait_until(qapp, lambda: sheets.kind == "homework")
    assert sheets.form["heading"] == "Edit homework"
    assert sheets.form["title"] == "History essay"
    sheets.forceClose()
    _settle(qapp, window)


def test_the_finish_button_marks_it_finished_and_offers_undo(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    essay = _block_named(root, "History essay")
    finish = _named(essay, "weekBlockFinish")[0]
    _click(window, finish)
    sheets = window._material_page.bridge.sheets
    assert sheets.kind == ""
    assert not sheets.active
    wait_until(
        qapp,
        lambda: not window.session.busy and bool(window.session.assignments["essay"].get("completed")),
    )
    wait_until(qapp, lambda: _snack(window) == "Finished History essay.")
    assert _bridge(window).property("snackAction") == "UNDO"
    bar = _qml(root, "materialSnackbar")
    _click(window, bar, dx=int(bar.property("width")) // 2 - 30)
    wait_until(
        qapp,
        lambda: not window.session.busy and not window.session.assignments["essay"].get("completed"),
    )
    _pump(qapp)
    assert _block_named(root, "History essay").property("done") is False


def test_the_finish_button_is_its_own_tab_stop_with_its_name(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    essay = _block_named(root, "History essay")
    assert essay.property("activeFocusOnTab") is True
    finish = _named(essay, "weekBlockFinish")[0]
    assert finish.property("activeFocusOnTab") is True
    face = QAccessible.queryAccessibleInterface(finish)
    assert face is not None
    assert face.text(QAccessible.Text.Name) == "Mark History essay finished"
    essay.forceActiveFocus()
    _pump(qapp)
    assert essay.property("activeFocus") is True
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Tab)
    _pump(qapp)
    assert finish.property("activeFocus") is True


def test_right_click_on_a_block_shows_edit_mark_finished_and_delete(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    essay = _block_named(root, "History essay")
    point = _centre(root, essay)
    QTest.mouseClick(window._material_page._quick, Qt.MouseButton.RightButton, pos=point)
    _pump(qapp)
    menu = _named(root, "blockMenu")[0]
    assert menu.property("open") is True
    entries = menu.property("entries").toVariant()
    labels = [e["label"] for e in entries]
    assert labels == ["Edit", "Mark finished", "Delete"]
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Escape)
    _pump(qapp)
    assert menu.property("open") is False
    assert essay.property("activeFocus") is True


def test_shift_f10_on_a_block_opens_the_same_menu(qapp: QApplication, window: NativeWindow) -> None:
    root = _reset(window, qapp)
    essay = _block_named(root, "History essay")
    essay.forceActiveFocus()
    _pump(qapp)
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier)
    _pump(qapp)
    menu = _named(root, "blockMenu")[0]
    assert menu.property("open") is True
    entries = menu.property("entries").toVariant()
    labels = [e["label"] for e in entries]
    assert labels == ["Edit", "Mark finished", "Delete"]
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Escape)
    _pump(qapp)
    assert menu.property("open") is False
    assert essay.property("activeFocus") is True


def test_editing_the_title_from_a_block_saves_and_undo_reverts_it(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    essay = _block_named(root, "History essay")
    _click(window, essay)
    sheets = window._material_page.bridge.sheets
    wait_until(qapp, lambda: sheets.kind == "homework")
    title_field = _named(root, "homeworkTitle")[0]
    title_input = _named(title_field, "fieldInput")[0]
    title_input.forceActiveFocus()
    _pump(qapp)
    title_input.selectAll()
    _pump(qapp)
    QTest.keyClicks(window._material_page._quick, "History essay, edited")
    _pump(qapp)
    assert sheets.form["title"] == "History essay, edited"
    next_btn = _named(root, "homeworkNext")[0]
    assert next_btn.property("text") == "Save"
    _click(window, next_btn)
    wait_until(
        qapp,
        lambda: window.session.assignments["essay"]["title"] == "History essay, edited",
    )
    _settle(qapp, window)
    wait_until(
        qapp,
        lambda: any(
            item.property("visible") and item.property("actionText") == "UNDO"
            for item in (_named(root, "sheetNotice") + _named(root, "materialSnackbar"))
        ),
    )
    notice = next(
        item
        for item in (_named(root, "sheetNotice") + _named(root, "materialSnackbar"))
        if item.property("visible") and item.property("actionText") == "UNDO"
    )
    # A notice alone must not hold the sheet layer: that would disable the app until it timed out.
    assert sheets.active is False
    assert root.property("sheetOpen") is False
    undo_btn = next(c for c in _visuals(notice) if str(c.property("text")) == "UNDO")
    _click(window, undo_btn)
    _settle(qapp, window)
    wait_until(
        qapp,
        lambda: window.session.assignments["essay"]["title"] == "History essay",
    )
    sheets.forceClose()
    _settle(qapp, window)


def test_clicking_a_drawer_card_opens_edit_and_dragging_it_still_places_it(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, "sheet", "Math worksheet", 30, due)
    settled(qapp, window)
    _pump(qapp)

    card = _named(root, "homeworkCard")[0]
    _click(window, card)
    sheets = window._material_page.bridge.sheets
    wait_until(qapp, lambda: sheets.kind == "homework")
    assert sheets.form["title"] == "Math worksheet"
    sheets.forceClose()
    _settle(qapp, window)
    _pump(qapp)

    card = _named(root, "homeworkCard")[0]
    grid = _qml(root, "weekScroller")
    hours_item = next(child for child in grid.childItems()[0].childItems() if child.property("width"))
    row = int(_bridge(window).property("hourRow"))
    gutter = int(_qml(root, "materialWeek").property("gutter"))
    day_width = float(_qml(root, "materialWeek").property("dayWidth"))
    friday = 4
    grid.setProperty("contentY", float(16 * row - 100))
    _pump(qapp)
    inside = hours_item.mapToScene(QPointF(gutter + friday * day_width + day_width / 2, 16 * row + 10))
    _drag(window, card, QPoint(int(inside.x()), int(inside.y())))
    wait_until(
        qapp,
        lambda: not window.session.busy and _qml(root, "homeworkCount").property("text") == "0",
    )
    placed = next(b for b in window.session.blocks if b.get("assignment_id") == "sheet")
    assert placed.get("start") == "16:00"
    assert sheets.kind == ""
    assert not sheets.active


def test_enter_on_a_drawer_card_opens_edit_and_place_now_is_in_its_menu(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, "sheet", "Math worksheet", 30, due)
    settled(qapp, window)
    _pump(qapp)

    card = _named(root, "homeworkCard")[0]
    card.forceActiveFocus()
    _pump(qapp)
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Return)
    sheets = window._material_page.bridge.sheets
    wait_until(qapp, lambda: sheets.kind == "homework")
    assert sheets.form["title"] == "Math worksheet"
    sheets.forceClose()
    _settle(qapp, window)
    _pump(qapp)

    card = _named(root, "homeworkCard")[0]
    card.forceActiveFocus()
    _pump(qapp)
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier)
    _pump(qapp)
    menu = _named(root, "cardMenu")[0]
    assert menu.property("open") is True
    entries = menu.property("entries").toVariant()
    labels = [e["label"] for e in entries]
    assert labels == ["Edit", "Place now", "Mark finished", "Delete"]
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Escape)
    _pump(qapp)
    assert menu.property("open") is False
    assert card.property("activeFocus") is True


def test_clicking_a_day_block_opens_edit_and_its_tick_still_finishes(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Day draws its hours with Week's blocks (J22): a click opens the homework, and the tick
    finishes it with Undo, as on Week."""
    root = _reset(window, qapp)
    monday = _week_monday(window)
    thursday = (monday + timedelta(days=3)).isoformat()
    window.session.open_day(thursday)
    _bridge(window).showPage("day")
    _pump(qapp)
    day = _qml(root, "materialDay")
    wait_until(qapp, lambda: _day_block(day, "History essay") is not None)
    _click(window, _day_block(day, "History essay"))
    sheets = window._material_page.bridge.sheets
    wait_until(qapp, lambda: sheets.kind == "homework")
    assert sheets.form["title"] == "History essay"
    sheets.forceClose()
    _settle(qapp, window)
    _pump(qapp)

    _click(window, _named(_day_block(day, "History essay"), "weekBlockFinish")[0])
    wait_until(
        qapp,
        lambda: not window.session.busy and bool(window.session.assignments["essay"].get("completed")),
    )
    wait_until(qapp, lambda: _snack(window) == "Finished History essay.")
    bar = _qml(root, "materialSnackbar")
    _click(window, bar, dx=int(bar.property("width")) // 2 - 30)
    wait_until(
        qapp,
        lambda: not window.session.busy and not window.session.assignments["essay"].get("completed"),
    )
    _bridge(window).showPage("week")


def _day_block(day: QObject, title: str) -> QObject | None:
    for block in _named(day, "weekBlock"):
        if any(str(label.property("text")) == title for label in _named(block, "title")):
            return block
    return None


def test_delete_from_the_block_menu_asks_first_and_can_be_undone(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    essay = _block_named(root, "History essay")
    essay.forceActiveFocus()
    _pump(qapp)
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier)
    _pump(qapp)
    menu = _named(root, "blockMenu")[0]
    assert menu.property("open") is True
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Down)
    _pump(qapp)
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Down)
    _pump(qapp)
    assert menu.property("cursor") == 2
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Return)
    _pump(qapp)

    sheets = window._material_page.bridge.sheets
    wait_until(qapp, lambda: sheets.ask.get("title") == "Delete homework")
    prompt = _named(root, "sheetPrompt")[0]
    assert prompt.property("visible") is True
    assert "essay" in window.session.assignments

    cancel_btn = _named(prompt, "prompt_stay")[0]
    _click(window, cancel_btn)
    _pump(qapp)
    assert sheets.ask == {}
    assert "essay" in window.session.assignments

    essay = _block_named(root, "History essay")
    essay.forceActiveFocus()
    _pump(qapp)
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier)
    _pump(qapp)
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Down)
    _pump(qapp)
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Down)
    _pump(qapp)
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Return)
    _pump(qapp)

    wait_until(qapp, lambda: sheets.ask.get("title") == "Delete homework")
    prompt = _named(root, "sheetPrompt")[0]
    assert prompt.property("visible") is True
    delete_btn = _named(prompt, "prompt_delete")[0]
    _click(window, delete_btn)
    wait_until(qapp, lambda: "essay" not in window.session.assignments)
    _settle(qapp, window)

    wait_until(
        qapp,
        lambda: any(
            item.property("visible") and item.property("actionText") == "UNDO"
            for item in (_named(root, "sheetNotice") + _named(root, "materialSnackbar"))
        ),
    )
    notice = next(
        item
        for item in (_named(root, "sheetNotice") + _named(root, "materialSnackbar"))
        if item.property("visible") and item.property("actionText") == "UNDO"
    )
    undo_btn = next(c for c in _visuals(notice) if str(c.property("text")) == "UNDO")
    _click(window, undo_btn)
    _settle(qapp, window)
    wait_until(qapp, lambda: "essay" in window.session.assignments)
    _settle(qapp, window)


def _find_menu_items(interface: QAccessibleInterface | None) -> list[QAccessibleInterface]:
    items: list[QAccessibleInterface] = []
    if interface is None:
        return items
    if interface.role() == QAccessible.Role.MenuItem:
        items.append(interface)
    for i in range(interface.childCount()):
        child = interface.child(i)
        if child is not None:
            items.extend(_find_menu_items(child))
    return items


def test_escape_on_the_block_menu_returns_focus_to_the_block(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    essay = _block_named(root, "History essay")
    essay.forceActiveFocus()
    _pump(qapp)
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier)
    _pump(qapp)
    menu = _named(root, "blockMenu")[0]
    assert menu.property("open") is True
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Escape)
    _pump(qapp)
    assert menu.property("open") is False
    assert essay.property("activeFocus") is True
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Return)
    sheets = window._material_page.bridge.sheets
    wait_until(qapp, lambda: sheets.kind == "homework")
    assert sheets.form["heading"] == "Edit homework"
    assert sheets.form["title"] == "History essay"
    sheets.forceClose()
    _settle(qapp, window)


def test_escape_on_the_card_menu_returns_focus_to_the_card(qapp: QApplication, window: NativeWindow) -> None:
    root = _reset(window, qapp)
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, "sheet", "Math worksheet", 30, due)
    settled(qapp, window)
    _pump(qapp)

    card = _named(root, "homeworkCard")[0]
    card.forceActiveFocus()
    _pump(qapp)
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier)
    _pump(qapp)
    menu = _named(root, "cardMenu")[0]
    assert menu.property("open") is True
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Escape)
    _pump(qapp)
    assert menu.property("open") is False
    assert card.property("activeFocus") is True
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Return)
    sheets = window._material_page.bridge.sheets
    wait_until(qapp, lambda: sheets.kind == "homework")
    assert sheets.form["heading"] == "Edit homework"
    assert sheets.form["title"] == "Math worksheet"
    sheets.forceClose()
    _settle(qapp, window)


def test_block_menu_rows_are_menu_items_a_screen_reader_can_press(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    essay = _block_named(root, "History essay")
    essay.forceActiveFocus()
    _pump(qapp)
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier)
    _pump(qapp)
    menu = _named(root, "blockMenu")[0]
    assert menu.property("open") is True
    interface = QAccessible.queryAccessibleInterface(menu)
    assert interface is not None
    menu_items = _find_menu_items(interface)
    names = [item.text(QAccessible.Text.Name) for item in menu_items]
    assert names == ["Edit", "Mark finished", "Delete"]
    mark_finished = next(item for item in menu_items if item.text(QAccessible.Text.Name) == "Mark finished")
    action = mark_finished.actionInterface()
    assert action is not None and "Press" in action.actionNames()
    action.doAction("Press")
    wait_until(
        qapp,
        lambda: not window.session.busy and bool(window.session.assignments["essay"].get("completed")),
    )
    _pump(qapp)
    assert _block_named(root, "History essay").property("done") is True


def test_a_long_title_does_not_run_under_the_finish_button(qapp: QApplication, window: NativeWindow) -> None:
    root = _reset(window, qapp)
    window.session.add_homework(
        {
            **window.session.assignments["essay"],
            "title": "WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW",
        }
    )
    window.session.save()
    settled(qapp, window)
    _pump(qapp)

    essay = _block_named(root, "WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW")
    finish = _named(essay, "weekBlockFinish")[0]
    title_item = next(child for child in _named(essay, "title") if child.property("text"))
    title_right = title_item.mapToItem(essay, QPointF(title_item.width(), 0)).x()
    finish_left = finish.mapToItem(essay, QPointF(0, 0)).x()
    assert title_right < finish_left
