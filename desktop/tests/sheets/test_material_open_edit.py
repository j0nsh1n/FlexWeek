"""Material week: a homework block or drawer card opens Edit homework on click, Enter and Space; the
finish tick finishes it with Undo; the block and card menus open from the pointer and the keyboard, close
on Esc with the keyboard back where it was, and are menus a screen reader can press."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QPoint, QPointF, Qt
from PySide6.QtGui import QAccessible, QAccessibleInterface
from PySide6.QtTest import QTest

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import named, pump, qml, visuals
from desktop.tests.sheets.support_material_sheets import (
    add_homework,
    block_named,
    bridge,
    centre,
    click,
    drag,
    material_week,
    snack,
    week_monday,
)
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp, settled  # noqa: F401

SHIFT = Qt.KeyboardModifier.ShiftModifier


def quick_of(window: NativeWindow):
    return window._material_page._quick


def finished(window: NativeWindow, done: bool) -> bool:
    return not window.session.busy and bool(window.session.assignments["essay"].get("completed")) is done


def open_sheet_is_homework(sheets) -> bool:
    return sheets.kind == "homework"


def close_sheet(qapp, window: NativeWindow, sheets) -> None:
    sheets.forceClose()
    settled(qapp, window)
    pump(qapp)


def drawer_card(qapp, window: NativeWindow, root: QObject) -> QObject:
    """A waiting homework, Math worksheet, in the drawer."""
    add_homework(window, "sheet", "Math worksheet", 30, (week_monday(window) + timedelta(days=6)).isoformat())
    pump(qapp)
    return named(root, "homeworkCard")[0]


def undo_notice(root: QObject) -> QObject | None:
    for item in named(root, "sheetNotice") + named(root, "materialSnackbar"):
        if item.property("visible") and item.property("actionText") == "UNDO":
            return item
    return None


def click_undo(window: NativeWindow, notice: QObject) -> None:
    click(window, next(c for c in visuals(notice) if str(c.property("text")) == "UNDO"))


def test_clicking_a_homework_block_opens_edit_and_keeps_it_unfinished(qapp, window: NativeWindow) -> None:
    root = material_week(qapp, window)
    assert window.session.assignments["essay"].get("completed") in (None, False)
    click(window, block_named(root, "History essay"))
    sheets = bridge(window).sheets
    wait_until(qapp, lambda: open_sheet_is_homework(sheets))
    assert sheets.form["heading"] == "Edit homework"
    assert sheets.form["title"] == "History essay"
    assert window.session.assignments["essay"].get("completed") in (None, False)


@pytest.mark.parametrize("key", [Qt.Key.Key_Return, Qt.Key.Key_Space], ids=["enter", "space"])
def test_enter_or_space_on_a_focused_block_opens_edit(qapp, window: NativeWindow, key) -> None:
    root = material_week(qapp, window)
    block_named(root, "History essay").forceActiveFocus()
    pump(qapp)
    QTest.keyClick(quick_of(window), key)
    sheets = bridge(window).sheets
    wait_until(qapp, lambda: open_sheet_is_homework(sheets))
    assert sheets.form["heading"] == "Edit homework"
    assert sheets.form["title"] == "History essay"


def test_the_finish_button_marks_it_finished_and_offers_undo(qapp, window: NativeWindow) -> None:
    root = material_week(qapp, window)
    finish = named(block_named(root, "History essay"), "weekBlockFinish")[0]
    click(window, finish)
    sheets = bridge(window).sheets
    assert sheets.kind == ""
    assert not sheets.active
    wait_until(qapp, lambda: finished(window, True))
    wait_until(qapp, lambda: snack(window) == "Finished History essay.")
    assert bridge(window).property("snackAction") == "UNDO"
    bar = qml(root, "materialSnackbar")
    click(window, bar, dx=int(bar.property("width")) // 2 - 30)
    wait_until(qapp, lambda: finished(window, False))
    pump(qapp)
    assert block_named(root, "History essay").property("done") is False


def test_the_finish_button_is_its_own_tab_stop_with_its_name(qapp, window: NativeWindow) -> None:
    root = material_week(qapp, window)
    essay = block_named(root, "History essay")
    assert essay.property("activeFocusOnTab") is True
    finish = named(essay, "weekBlockFinish")[0]
    assert finish.property("activeFocusOnTab") is True
    face = QAccessible.queryAccessibleInterface(finish)
    assert face is not None
    assert face.text(QAccessible.Text.Name) == "Mark History essay finished"
    essay.forceActiveFocus()
    pump(qapp)
    assert essay.property("activeFocus") is True
    QTest.keyClick(quick_of(window), Qt.Key.Key_Tab)
    pump(qapp)
    assert finish.property("activeFocus") is True


@pytest.mark.parametrize("how", ["right-click", "shift-f10"])
def test_the_block_menu_lists_edit_mark_finished_and_delete_and_escape_returns_to_the_block(
    qapp, window: NativeWindow, how
) -> None:
    root = material_week(qapp, window)
    essay = block_named(root, "History essay")
    if how == "right-click":
        QTest.mouseClick(quick_of(window), Qt.MouseButton.RightButton, pos=centre(essay))
    else:
        essay.forceActiveFocus()
        pump(qapp)
        QTest.keyClick(quick_of(window), Qt.Key.Key_F10, SHIFT)
    pump(qapp)
    menu = named(root, "blockMenu")[0]
    assert menu.property("open") is True
    assert [e["label"] for e in menu.property("entries").toVariant()] == ["Edit", "Mark finished", "Delete"]
    QTest.keyClick(quick_of(window), Qt.Key.Key_Escape)
    pump(qapp)
    assert menu.property("open") is False
    assert essay.property("activeFocus") is True


def test_enter_after_escape_on_the_block_menu_opens_edit(qapp, window: NativeWindow) -> None:
    root = material_week(qapp, window)
    essay = block_named(root, "History essay")
    essay.forceActiveFocus()
    pump(qapp)
    QTest.keyClick(quick_of(window), Qt.Key.Key_F10, SHIFT)
    pump(qapp)
    menu = named(root, "blockMenu")[0]
    assert menu.property("open") is True
    QTest.keyClick(quick_of(window), Qt.Key.Key_Escape)
    pump(qapp)
    assert menu.property("open") is False
    QTest.keyClick(quick_of(window), Qt.Key.Key_Return)
    sheets = bridge(window).sheets
    wait_until(qapp, lambda: open_sheet_is_homework(sheets))
    assert sheets.form["heading"] == "Edit homework"
    assert sheets.form["title"] == "History essay"


def test_editing_the_title_from_a_block_saves_and_undo_reverts_it(qapp, window: NativeWindow) -> None:
    root = material_week(qapp, window)
    click(window, block_named(root, "History essay"))
    sheets = bridge(window).sheets
    wait_until(qapp, lambda: open_sheet_is_homework(sheets))
    title_input = named(named(root, "homeworkTitle")[0], "fieldInput")[0]
    title_input.forceActiveFocus()
    pump(qapp)
    title_input.selectAll()
    pump(qapp)
    QTest.keyClicks(quick_of(window), "History essay, edited")
    pump(qapp)
    assert sheets.form["title"] == "History essay, edited"
    next_btn = named(root, "homeworkNext")[0]
    assert next_btn.property("text") == "Save"
    click(window, next_btn)
    wait_until(qapp, lambda: window.session.assignments["essay"]["title"] == "History essay, edited")
    settled(qapp, window)
    wait_until(qapp, lambda: undo_notice(root) is not None)
    # A notice alone must not hold the sheet layer: that would disable the app until it timed out.
    assert sheets.active is False
    assert root.property("sheetOpen") is False
    click_undo(window, undo_notice(root))
    settled(qapp, window)
    wait_until(qapp, lambda: window.session.assignments["essay"]["title"] == "History essay")


def test_clicking_a_drawer_card_opens_edit_and_dragging_it_still_places_it(
    qapp, window: NativeWindow
) -> None:
    root = material_week(qapp, window)
    card = drawer_card(qapp, window, root)
    click(window, card)
    sheets = bridge(window).sheets
    wait_until(qapp, lambda: open_sheet_is_homework(sheets))
    assert sheets.form["title"] == "Math worksheet"
    close_sheet(qapp, window, sheets)

    card = named(root, "homeworkCard")[0]
    grid = qml(root, "weekScroller")
    hours_item = next(child for child in grid.childItems()[0].childItems() if child.property("width"))
    row = int(bridge(window).property("hourRow"))
    gutter = int(qml(root, "materialWeek").property("gutter"))
    day_width = float(qml(root, "materialWeek").property("dayWidth"))
    friday = 4
    grid.setProperty("contentY", float(16 * row - 100))
    pump(qapp)
    inside = hours_item.mapToScene(QPointF(gutter + friday * day_width + day_width / 2, 16 * row + 10))
    drag(window, card, QPoint(int(inside.x()), int(inside.y())))
    wait_until(
        qapp,
        lambda: not window.session.busy and qml(root, "homeworkCount").property("text") == "0",
    )
    placed = next(b for b in window.session.blocks if b.get("assignment_id") == "sheet")
    assert placed.get("start") == "16:00"
    assert sheets.kind == ""
    assert not sheets.active


def test_enter_on_a_drawer_card_opens_edit_and_place_now_is_in_its_menu(qapp, window: NativeWindow) -> None:
    root = material_week(qapp, window)
    card = drawer_card(qapp, window, root)
    card.forceActiveFocus()
    pump(qapp)
    QTest.keyClick(quick_of(window), Qt.Key.Key_Return)
    sheets = bridge(window).sheets
    wait_until(qapp, lambda: open_sheet_is_homework(sheets))
    assert sheets.form["title"] == "Math worksheet"
    close_sheet(qapp, window, sheets)

    card = named(root, "homeworkCard")[0]
    card.forceActiveFocus()
    pump(qapp)
    QTest.keyClick(quick_of(window), Qt.Key.Key_F10, SHIFT)
    pump(qapp)
    menu = named(root, "cardMenu")[0]
    assert menu.property("open") is True
    assert [e["label"] for e in menu.property("entries").toVariant()] == [
        "Edit",
        "Place now",
        "Mark finished",
        "Delete",
    ]


def test_escape_on_the_card_menu_returns_focus_to_the_card_and_enter_opens_edit(
    qapp, window: NativeWindow
) -> None:
    root = material_week(qapp, window)
    card = drawer_card(qapp, window, root)
    card.forceActiveFocus()
    pump(qapp)
    QTest.keyClick(quick_of(window), Qt.Key.Key_F10, SHIFT)
    pump(qapp)
    menu = named(root, "cardMenu")[0]
    assert menu.property("open") is True
    QTest.keyClick(quick_of(window), Qt.Key.Key_Escape)
    pump(qapp)
    assert menu.property("open") is False
    assert card.property("activeFocus") is True
    QTest.keyClick(quick_of(window), Qt.Key.Key_Return)
    sheets = bridge(window).sheets
    wait_until(qapp, lambda: open_sheet_is_homework(sheets))
    assert sheets.form["heading"] == "Edit homework"
    assert sheets.form["title"] == "Math worksheet"


def test_clicking_a_day_block_opens_edit_and_its_tick_still_finishes(qapp, window: NativeWindow) -> None:
    """Day draws its hours with Week's blocks: a click opens the homework, and the tick finishes it with
    Undo, as on Week."""
    root = material_week(qapp, window)
    thursday = (week_monday(window) + timedelta(days=3)).isoformat()
    window.session.open_day(thursday)
    bridge(window).showPage("day")
    pump(qapp)
    day = qml(root, "materialDay")
    wait_until(qapp, lambda: day_block(day, "History essay") is not None)
    click(window, day_block(day, "History essay"))
    sheets = bridge(window).sheets
    wait_until(qapp, lambda: open_sheet_is_homework(sheets))
    assert sheets.form["title"] == "History essay"
    close_sheet(qapp, window, sheets)

    click(window, named(day_block(day, "History essay"), "weekBlockFinish")[0])
    wait_until(qapp, lambda: finished(window, True))
    wait_until(qapp, lambda: snack(window) == "Finished History essay.")
    bar = qml(root, "materialSnackbar")
    click(window, bar, dx=int(bar.property("width")) // 2 - 30)
    wait_until(qapp, lambda: finished(window, False))


def day_block(day: QObject, title: str) -> QObject | None:
    for block in named(day, "weekBlock"):
        if any(str(label.property("text")) == title for label in named(block, "title")):
            return block
    return None


def open_delete_prompt(qapp, window: NativeWindow, root: QObject):
    essay = block_named(root, "History essay")
    essay.forceActiveFocus()
    pump(qapp)
    QTest.keyClick(quick_of(window), Qt.Key.Key_F10, SHIFT)
    pump(qapp)
    menu = named(root, "blockMenu")[0]
    assert menu.property("open") is True
    for _ in range(2):
        QTest.keyClick(quick_of(window), Qt.Key.Key_Down)
        pump(qapp)
    assert menu.property("cursor") == 2
    QTest.keyClick(quick_of(window), Qt.Key.Key_Return)
    sheets = bridge(window).sheets
    wait_until(qapp, lambda: sheets.ask.get("title") == "Delete homework")
    prompt = named(root, "sheetPrompt")[0]
    assert prompt.property("visible") is True
    return sheets, prompt


def test_delete_from_the_block_menu_asks_first_and_can_be_undone(qapp, window: NativeWindow) -> None:
    root = material_week(qapp, window)
    sheets, prompt = open_delete_prompt(qapp, window, root)
    assert "essay" in window.session.assignments

    click(window, named(prompt, "prompt_stay")[0])
    pump(qapp)
    assert sheets.ask == {}
    assert "essay" in window.session.assignments

    sheets, prompt = open_delete_prompt(qapp, window, root)
    click(window, named(prompt, "prompt_delete")[0])
    wait_until(qapp, lambda: "essay" not in window.session.assignments)
    settled(qapp, window)

    wait_until(qapp, lambda: undo_notice(root) is not None)
    click_undo(window, undo_notice(root))
    settled(qapp, window)
    wait_until(qapp, lambda: "essay" in window.session.assignments)


def menu_items(interface: QAccessibleInterface | None) -> list[QAccessibleInterface]:
    items: list[QAccessibleInterface] = []
    if interface is None:
        return items
    if interface.role() == QAccessible.Role.MenuItem:
        items.append(interface)
    for i in range(interface.childCount()):
        child = interface.child(i)
        if child is not None:
            items.extend(menu_items(child))
    return items


def test_block_menu_rows_are_menu_items_a_screen_reader_can_press(qapp, window: NativeWindow) -> None:
    root = material_week(qapp, window)
    block_named(root, "History essay").forceActiveFocus()
    pump(qapp)
    QTest.keyClick(quick_of(window), Qt.Key.Key_F10, SHIFT)
    pump(qapp)
    menu = named(root, "blockMenu")[0]
    assert menu.property("open") is True
    interface = QAccessible.queryAccessibleInterface(menu)
    assert interface is not None
    items = menu_items(interface)
    assert [item.text(QAccessible.Text.Name) for item in items] == ["Edit", "Mark finished", "Delete"]
    mark_finished = next(item for item in items if item.text(QAccessible.Text.Name) == "Mark finished")
    action = mark_finished.actionInterface()
    assert action is not None and "Press" in action.actionNames()
    action.doAction("Press")
    wait_until(qapp, lambda: finished(window, True))
    pump(qapp)
    assert block_named(root, "History essay").property("done") is True
