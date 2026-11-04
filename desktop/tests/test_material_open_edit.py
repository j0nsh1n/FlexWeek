"""Material design: opening homework for editing on click/Enter/Space, finish button, context menus."""

from __future__ import annotations

import os
from datetime import timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

pytest_plugins = ["desktop.tests.test_material_week"]

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QAccessible  # noqa: E402
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
    _reset,
    _snack,
    _week_monday,
)


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


def test_enter_on_a_focused_block_opens_edit(
    qapp: QApplication, window: NativeWindow
) -> None:
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


def test_space_on_a_focused_block_opens_edit(
    qapp: QApplication, window: NativeWindow
) -> None:
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
    wait_until(
        qapp,
        lambda: not window.session.busy
        and bool(window.session.assignments["essay"].get("completed")),
    )
    wait_until(qapp, lambda: _snack(window) == "Finished History essay.")
    assert _bridge(window).property("snackAction") == "UNDO"
    bar = _qml(root, "materialSnackbar")
    _click(window, bar, dx=int(bar.property("width")) // 2 - 30)
    wait_until(
        qapp,
        lambda: not window.session.busy
        and not window.session.assignments["essay"].get("completed"),
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


def test_shift_f10_on_a_block_opens_the_same_menu(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    essay = _block_named(root, "History essay")
    essay.forceActiveFocus()
    _pump(qapp)
    QTest.keyClick(
        window._material_page._quick, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier
    )
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
    sheets.setText("title", "History essay, edited")
    sheets.save()
    wait_until(
        qapp,
        lambda: window.session.assignments["essay"]["title"]
        == "History essay, edited",
    )
    _settle(qapp, window)
    window.session.undo()
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
    hours_item = next(
        child
        for child in grid.childItems()[0].childItems()
        if child.property("width")
    )
    row = int(_bridge(window).property("hourRow"))
    gutter = int(_qml(root, "materialWeek").property("gutter"))
    day_width = float(_qml(root, "materialWeek").property("dayWidth"))
    friday = 4
    grid.setProperty("contentY", float(16 * row - 100))
    _pump(qapp)
    inside = hours_item.mapToScene(
        QPointF(gutter + friday * day_width + day_width / 2, 16 * row + 10)
    )
    _drag(window, card, QPoint(int(inside.x()), int(inside.y())))
    wait_until(
        qapp,
        lambda: not window.session.busy
        and _qml(root, "homeworkCount").property("text") == "0",
    )
    placed = next(
        b for b in window.session.blocks if b.get("assignment_id") == "sheet"
    )
    assert placed.get("start") == "16:00"


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
    QTest.keyClick(
        window._material_page._quick, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier
    )
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


def test_clicking_a_day_row_opens_edit_and_its_finish_button_still_finishes(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    monday = _week_monday(window)
    thursday = (monday + timedelta(days=3)).isoformat()
    window.session.open_day(thursday)
    _bridge(window).showPage("day")
    _pump(qapp)
    wait_until(qapp, lambda: len(_named(root, "dayFinish")) > 0)
    row = next(r for r in _named(root, "dayRow0") if r.property("title") == "History essay")
    _click(window, row)
    sheets = window._material_page.bridge.sheets
    wait_until(qapp, lambda: sheets.kind == "homework")
    assert sheets.form["title"] == "History essay"
    sheets.forceClose()
    _settle(qapp, window)
    _pump(qapp)

    finish_btn = _named(root, "dayFinish")[0]
    _click(window, finish_btn)
    wait_until(
        qapp,
        lambda: not window.session.busy
        and bool(window.session.assignments["essay"].get("completed")),
    )
    assert _bridge(window).property("snackText") == "Finished History essay"
    _bridge(window).showPage("week")


def test_delete_from_the_block_menu_asks_first_and_can_be_undone(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    essay = _block_named(root, "History essay")
    essay.forceActiveFocus()
    _pump(qapp)
    QTest.keyClick(
        window._material_page._quick, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier
    )
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
    assert "essay" in window.session.assignments

    sheets.answer("stay")
    _pump(qapp)
    assert sheets.ask == {}
    assert "essay" in window.session.assignments

    essay = _block_named(root, "History essay")
    essay.forceActiveFocus()
    _pump(qapp)
    QTest.keyClick(
        window._material_page._quick, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier
    )
    _pump(qapp)
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Down)
    _pump(qapp)
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Down)
    _pump(qapp)
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Return)
    _pump(qapp)

    wait_until(qapp, lambda: sheets.ask.get("title") == "Delete homework")
    sheets.answer("delete")
    wait_until(qapp, lambda: "essay" not in window.session.assignments)

    window.session.undo()
    _settle(qapp, window)
    _pump(qapp)
    wait_until(qapp, lambda: "essay" in window.session.assignments)
