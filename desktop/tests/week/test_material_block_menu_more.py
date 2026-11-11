"""The Material block menu gains Duplicate, Move to day... and Copy, for fixed times and homework, in Week and
Day (Jonathan, 2026-11-10). Each works from the mouse and from the keyboard; Move to day... opens a second
list of the week's days with today marked, arrows and Enter work in it, and Esc comes back to the block menu.
Undo takes back a Duplicate and a move. Copy fills the clipboard and Ctrl+V pastes it, as in the plain look.

Expected values come from the seeded week: Club on Thursday 17:30 for an hour, School Monday to Friday
mornings, the History essay planned Thursday 18:45, and the one clock at Thursday 19:00.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QComboBox  # noqa: E402

from desktop.native.widgets import PreviewDialog  # noqa: E402
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
FRIDAY = 4
FIXED = ["Edit", "Duplicate", "Move to day...", "Copy", "Delete"]
HOMEWORK = ["Edit", "Duplicate", "Move to day...", "Copy", "Mark finished", "Delete"]


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


def on_screen(qapp, window: NativeWindow, screen: str, title: str) -> QObject:
    """Material on Week or on Day (Thursday), and the named block there."""
    root = material_week(qapp, window)
    seed_club(qapp, window)
    if screen == "week":
        return block_named(root, title)
    window.session.open_day((week_monday(window) + timedelta(days=THURSDAY)).isoformat())
    bridge(window).showPage("day")
    pump(qapp)
    day = qml(root, "materialDay")
    wait_until(
        qapp,
        lambda: any(
            any(str(label.property("text")) == title for label in named(block, "title"))
            for block in named(day, "weekBlock")
        ),
    )
    return day_block(day, title)


def open_menu(qapp, window: NativeWindow, block: QObject, how: str) -> QObject:
    block.forceActiveFocus()
    pump(qapp)
    if how == "right-click":
        QTest.mouseClick(quick_of(window), Qt.MouseButton.RightButton, pos=centre(block))
    elif how == "shift-f10":
        QTest.keyClick(quick_of(window), Qt.Key.Key_F10, SHIFT)
    else:
        QTest.keyClick(quick_of(window), Qt.Key.Key_Menu)
    pump(qapp)
    return named(window._material_page.root, "blockMenu")[0]


def entries(menu: QObject) -> list[str]:
    return [item["label"] for item in menu.property("entries").toVariant()]


def key(qapp, window: NativeWindow, which: Qt.Key) -> None:
    QTest.keyClick(quick_of(window), which)
    pump(qapp, 10)


def choose_by_keyboard(qapp, window: NativeWindow, menu: QObject, label: str) -> None:
    for _ in range(entries(menu).index(label)):
        key(qapp, window, Qt.Key.Key_Down)
    key(qapp, window, Qt.Key.Key_Return)


def choose_by_mouse(qapp, window: NativeWindow, menu: QObject, label: str) -> None:
    """A real click on the row, found from the menu's top and the 44 px a row is."""
    index = entries(menu).index(label)
    top = named(menu, "shape")[0].mapToScene(QPointF(100, 8 + 44 * index + 22))
    QTest.mouseClick(quick_of(window), Qt.MouseButton.LeftButton, pos=QPoint(int(top.x()), int(top.y())))
    pump(qapp, 10)


def accept_preview_on(monkeypatch: pytest.MonkeyPatch, day_index: int) -> list[str]:
    """The paste preview, answered as the plain look's tests do: put the copy on a free day, save it."""
    seen: list[str] = []

    def preview(dialog: PreviewDialog) -> int:
        seen.append("preview")
        dialog.show()
        dialog.findChild(QComboBox, "previewDay0").setCurrentIndex(day_index)
        QTest.mouseClick(dialog.confirm, Qt.MouseButton.LeftButton)
        return dialog.result()

    monkeypatch.setattr(PreviewDialog, "exec", preview)
    return seen


def count(window: NativeWindow, title: str) -> int:
    return sum(1 for item in window.session.blocks if item.get("title") == title)


@pytest.mark.parametrize("screen", ["week", "day"])
@pytest.mark.parametrize("how", ["right-click", "shift-f10", "menu-key"])
def test_a_fixed_blocks_menu_lists_the_new_items_in_order(
    qapp, window: NativeWindow, screen: str, how: str
) -> None:
    block = on_screen(qapp, window, screen, "Club")
    menu = open_menu(qapp, window, block, how)
    assert entries(menu) == FIXED


@pytest.mark.parametrize("screen", ["week", "day"])
def test_a_homework_blocks_menu_lists_the_new_items_in_order(
    qapp, window: NativeWindow, screen: str
) -> None:
    block = on_screen(qapp, window, screen, "History essay")
    menu = open_menu(qapp, window, block, "right-click")
    assert entries(menu) == HOMEWORK


@pytest.mark.parametrize("screen", ["week", "day"])
@pytest.mark.parametrize("how", ["mouse", "keyboard"])
def test_duplicate_adds_a_copy_and_undo_takes_it_back(
    qapp, window: NativeWindow, monkeypatch: pytest.MonkeyPatch, screen: str, how: str
) -> None:
    block = on_screen(qapp, window, screen, "Club")
    seen = accept_preview_on(monkeypatch, FRIDAY)
    menu = open_menu(qapp, window, block, "shift-f10" if how == "keyboard" else "right-click")
    (choose_by_keyboard if how == "keyboard" else choose_by_mouse)(qapp, window, menu, "Duplicate")
    settled(qapp, window)
    assert seen == ["preview"]
    assert count(window, "Club") == 2
    bridge(window).undo()
    settled(qapp, window)
    assert count(window, "Club") == 1


@pytest.mark.parametrize("screen", ["week", "day"])
@pytest.mark.parametrize("how", ["mouse", "keyboard"])
def test_copy_fills_the_clipboard_and_ctrl_v_pastes_it(
    qapp, window: NativeWindow, monkeypatch: pytest.MonkeyPatch, screen: str, how: str
) -> None:
    block = on_screen(qapp, window, screen, "Club")
    menu = open_menu(qapp, window, block, "shift-f10" if how == "keyboard" else "right-click")
    (choose_by_keyboard if how == "keyboard" else choose_by_mouse)(qapp, window, menu, "Copy")
    assert window.session.clipboard is not None
    assert "Club" in window.session.clipboard["label"]
    assert count(window, "Club") == 1, "copying changes nothing"
    seen = accept_preview_on(monkeypatch, FRIDAY)
    QTest.keyClick(quick_of(window), Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    pump(qapp, 20)
    settled(qapp, window)
    assert seen == ["preview"]
    assert count(window, "Club") == 2


def test_ctrl_v_with_nothing_copied_changes_nothing(qapp, window: NativeWindow) -> None:
    on_screen(qapp, window, "week", "Club")
    QTest.keyClick(quick_of(window), Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    pump(qapp, 20)
    assert count(window, "Club") == 1


@pytest.mark.parametrize("screen", ["week", "day"])
@pytest.mark.parametrize("title, other", [("Club", "fixed"), ("History essay", "homework")])
def test_move_to_day_lists_the_days_with_today_marked_and_esc_returns_to_the_block_menu(
    qapp, window: NativeWindow, screen: str, title: str, other: str
) -> None:
    block = on_screen(qapp, window, screen, title)
    menu = open_menu(qapp, window, block, "shift-f10")
    choose_by_keyboard(qapp, window, menu, "Move to day...")
    assert menu.property("open") is True
    days = entries(menu)
    assert [day.split()[0] for day in days] == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    assert [day for day in days if "today" in day] == [days[THURSDAY]]
    key(qapp, window, Qt.Key.Key_Escape)
    assert menu.property("open") is True, "Esc goes back to the block menu"
    assert entries(menu) == (FIXED if other == "fixed" else HOMEWORK)
    key(qapp, window, Qt.Key.Key_Escape)
    assert menu.property("open") is False


@pytest.mark.parametrize("screen", ["week", "day"])
@pytest.mark.parametrize("how", ["mouse", "keyboard"])
def test_moving_to_another_day_keeps_the_time_and_undo_puts_it_back(
    qapp, window: NativeWindow, screen: str, how: str
) -> None:
    block = on_screen(qapp, window, screen, "Club")
    menu = open_menu(qapp, window, block, "shift-f10" if how == "keyboard" else "right-click")
    (choose_by_keyboard if how == "keyboard" else choose_by_mouse)(qapp, window, menu, "Move to day...")
    if how == "keyboard":
        # The list opens with the block's own day under the cursor: Friday is one Down from Thursday.
        for _ in range(FRIDAY - THURSDAY):
            key(qapp, window, Qt.Key.Key_Down)
        key(qapp, window, Qt.Key.Key_Return)
    else:
        choose_by_mouse(qapp, window, menu, entries(menu)[FRIDAY])
    settled(qapp, window)
    club = next(item for item in window.session.blocks if item["id"] == "club")
    assert club["days"] == [FRIDAY] and club["start"] == "17:30" and club["duration_min"] == 60
    assert menu.property("open") is False
    bridge(window).undo()
    settled(qapp, window)
    club = next(item for item in window.session.blocks if item["id"] == "club")
    assert club["days"] == [THURSDAY] and club["start"] == "17:30"


def test_moving_homework_to_another_day_keeps_its_time(qapp, window: NativeWindow) -> None:
    block = on_screen(qapp, window, "week", "History essay")
    menu = open_menu(qapp, window, block, "shift-f10")
    choose_by_keyboard(qapp, window, menu, "Move to day...")
    for _ in range(FRIDAY - THURSDAY):
        key(qapp, window, Qt.Key.Key_Down)
    key(qapp, window, Qt.Key.Key_Return)
    settled(qapp, window)
    essay = next(item for item in window.session.blocks if item.get("assignment_id") == "essay")
    assert essay["days"] == [FRIDAY] and essay["start"] == "18:45"
