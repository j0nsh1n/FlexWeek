"""A fixed block in Material Week and Day has a menu, as homework has: Edit and Delete, opened by a
right-click, Shift+F10 or the Menu key. Arrow keys move in it, Esc closes it with the keyboard back on the
block, Edit opens Edit fixed time, and Delete asks the same question the Edit sheet asks and deletes the
same way. Homework's menu is unchanged (sheets/test_material_open_edit.py).

Expected values come from the block seeded here: Club, Thursday 17:30 for an hour.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import window  # noqa: E402,F401
from desktop.tests.material_support import named, pump, qml  # noqa: E402
from desktop.tests.sheets.support_material_sheets import (  # noqa: E402
    block_named,
    bridge,
    centre,
    material_week,
    week_monday,
)
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.window_support import qapp, settled  # noqa: E402,F401

SHIFT = Qt.KeyboardModifier.ShiftModifier
THURSDAY = 3


def quick_of(window: NativeWindow):
    return window._material_page._quick


def seed_club(qapp, window: NativeWindow) -> None:
    window.session.add_block(
        {
            "id": "club",
            "title": "Club",
            "kind": "locked",
            "category": "extra",
            "start": "17:30",
            "duration_min": 60,
            "days": [THURSDAY],
        }
    )
    window.session.save()
    settled(qapp, window)
    pump(qapp)


def day_block(day: QObject, title: str) -> QObject:
    for block in named(day, "weekBlock"):
        if any(str(label.property("text")) == title for label in named(block, "title")):
            return block
    raise AssertionError(f"no block named {title} on Day")


def club_on(qapp, window: NativeWindow, screen: str) -> tuple[QObject, QObject]:
    """Material on Week or on Day (opened on Thursday), and the Club block there."""
    root = material_week(qapp, window)
    seed_club(qapp, window)
    if screen == "week":
        return root, block_named(root, "Club")
    on_day = (week_monday(window) + timedelta(days=THURSDAY)).isoformat()
    window.session.open_day(on_day)
    bridge(window).showPage("day")
    pump(qapp)
    day = qml(root, "materialDay")
    wait_until(
        qapp,
        lambda: any(
            any(str(label.property("text")) == "Club" for label in named(block, "title"))
            for block in named(day, "weekBlock")
        ),
    )
    return root, day_block(day, "Club")


def open_menu(qapp, window: NativeWindow, block: QObject, how: str) -> QObject:
    if how == "right-click":
        # Focus scrolls the block into view, as the student's own scrolling would; a block above the
        # visible hours cannot be right-clicked.
        block.forceActiveFocus()
        pump(qapp)
        QTest.mouseClick(quick_of(window), Qt.MouseButton.RightButton, pos=centre(block))
    else:
        block.forceActiveFocus()
        pump(qapp)
        if how == "shift-f10":
            QTest.keyClick(quick_of(window), Qt.Key.Key_F10, SHIFT)
        else:
            QTest.keyClick(quick_of(window), Qt.Key.Key_Menu)
    pump(qapp)
    return named(qml_root(window), "blockMenu")[0]


def qml_root(window: NativeWindow) -> QObject:
    return window._material_page.root


def entries(menu: QObject) -> list[str]:
    return [item["label"] for item in menu.property("entries").toVariant()]


@pytest.mark.parametrize("screen", ["week", "day"])
@pytest.mark.parametrize("how", ["right-click", "shift-f10", "menu-key"])
def test_a_fixed_block_opens_a_menu_with_edit_and_delete_and_escape_returns_to_it(
    qapp, window: NativeWindow, screen: str, how: str
) -> None:
    _root, block = club_on(qapp, window, screen)
    menu = open_menu(qapp, window, block, how)
    assert menu.property("open") is True
    assert entries(menu) == ["Edit", "Delete"]
    QTest.keyClick(quick_of(window), Qt.Key.Key_Escape)
    pump(qapp)
    assert menu.property("open") is False
    assert block.property("activeFocus") is True


@pytest.mark.parametrize("screen", ["week", "day"])
def test_arrow_keys_move_in_the_menu_and_edit_opens_edit_fixed_time(
    qapp, window: NativeWindow, screen: str
) -> None:
    _root, block = club_on(qapp, window, screen)
    menu = open_menu(qapp, window, block, "shift-f10")
    assert menu.property("cursor") == 0
    QTest.keyClick(quick_of(window), Qt.Key.Key_Down)
    assert menu.property("cursor") == 1
    QTest.keyClick(quick_of(window), Qt.Key.Key_Up)
    assert menu.property("cursor") == 0
    QTest.keyClick(quick_of(window), Qt.Key.Key_Return)
    sheets = bridge(window).sheets
    wait_until(qapp, lambda: sheets.kind == "block")
    assert sheets.form["heading"] == "Edit fixed time"
    assert sheets.form["title"] == "Club"
    sheets.forceClose()
    pump(qapp)


def edit_sheets_delete_question(qapp, window: NativeWindow) -> dict:
    """What the Edit fixed time sheet's Delete asks for Club on Thursday."""
    sheets = bridge(window).sheets
    sheets.editBlock("club", THURSDAY)
    pump(qapp)
    sheets.remove()
    asked = dict(sheets.ask)
    sheets.forceClose()
    pump(qapp)
    return asked


@pytest.mark.parametrize("screen", ["week", "day"])
def test_delete_asks_the_edit_sheets_question_then_deletes_the_same_way(
    qapp, window: NativeWindow, screen: str
) -> None:
    _root, block = club_on(qapp, window, screen)
    sheets = bridge(window).sheets
    expected = edit_sheets_delete_question(qapp, window)
    assert expected["title"] == "Delete fixed time"
    menu = open_menu(qapp, window, block, "right-click")
    QTest.keyClick(quick_of(window), Qt.Key.Key_Down)
    QTest.keyClick(quick_of(window), Qt.Key.Key_Return)
    pump(qapp)
    assert menu.property("open") is False
    assert dict(sheets.ask) == expected
    assert sheets.kind == "", "the question stands alone: no sheet opened behind it"
    sheets.answer("stay")
    pump(qapp)
    assert any(item["id"] == "club" for item in window.session.blocks), "Cancel deletes nothing"
    assert sheets.ask == {}
    menu = open_menu(qapp, window, block, "shift-f10")
    QTest.keyClick(quick_of(window), Qt.Key.Key_Down)
    QTest.keyClick(quick_of(window), Qt.Key.Key_Return)
    pump(qapp)
    sheets.answer("delete")
    settled(qapp, window)
    assert not any(item["id"] == "club" for item in window.session.blocks)
    assert sheets.notice == "Deleted Club from this week."
