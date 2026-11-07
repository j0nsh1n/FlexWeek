"""The week grid is one Tab stop a student works with the arrow keys, with a ring that shows where they
are; Shift+F10 and the Menu key ask for the menu at that slot."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QAbstractButton, QApplication, QDialog  # noqa: E402

from desktop.native.hours.geometry import Axis  # noqa: E402
from desktop.native.layouts.registry import sanitize_layout  # noqa: E402
from desktop.native.widgets import BlockDialog  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import window  # noqa: E402, F401
from desktop.tests.week.support_hand import (  # noqa: E402, F401
    NONE,
    PIANO,
    WEDNESDAY,
    add_piano,
    classic_window,
    grid,
    hold_clock,
    key,
    menus,
    tab_to_grid,
)
from desktop.tests.window_support import qapp, settled  # noqa: E402, F401


@pytest.mark.parametrize(
    ("which", "mods"),
    [(Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier), (Qt.Key.Key_Menu, NONE)],
)
def test_the_menu_keys_ask_at_the_next_free_quarter_hour_after_now_without_scrolling(
    qapp: QApplication,
    classic_window: NativeWindow,
    menus: list[dict],
    which: Qt.Key,
    mods: Qt.KeyboardModifier,
) -> None:
    hold_clock(classic_window, WEDNESDAY, 20 * 60 + 7)
    hours = grid(classic_window)
    bar = classic_window.week_table.scroll.verticalScrollBar()
    hours.setFocus(Qt.FocusReason.MouseFocusReason)
    bar.setValue(0)
    qapp.processEvents()
    assert not hours.in_view(WEDNESDAY, 20 * 60 + 15), "the slot has to start off screen"
    key(classic_window, which, mods)
    assert [shown["rows"][0] for shown in menus] == ["Add fixed time at 8:15 PM"]
    assert bar.value() == 0, "the menu key scrolled the grid"
    assert hours.focus_slot() == (WEDNESDAY, 20 * 60 + 15)


def test_the_menu_key_skips_slots_that_are_taken(
    qapp: QApplication, classic_window: NativeWindow, menus: list[dict]
) -> None:
    classic_window.session.add_block({**PIANO, "id": "now", "start": "14:00", "duration_min": 45})
    classic_window.session.save()
    settled(qapp, classic_window)
    hold_clock(classic_window, WEDNESDAY, 14 * 60 + 7)
    grid(classic_window).setFocus(Qt.FocusReason.MouseFocusReason)
    key(classic_window, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier)
    assert [shown["rows"][0] for shown in menus] == ["Add fixed time at 2:45 PM"]


def test_the_grid_is_one_tab_stop_and_shows_where_the_student_is(
    qapp: QApplication, classic_window: NativeWindow
) -> None:
    hours = grid(classic_window)
    tab_to_grid(classic_window)
    assert hours.ring_shown and hours.focus_slot() == (WEDNESDAY, 14 * 60 + 15)
    key(classic_window, Qt.Key.Key_Tab)
    assert not classic_window.week_table.isAncestorOf(classic_window.focusWidget()), (
        "Tab stayed inside the grid"
    )
    key(classic_window, Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
    assert classic_window.focusWidget() is hours, "Shift+Tab did not come straight back to the grid"


def test_a_click_gives_the_grid_focus_without_a_ring(
    qapp: QApplication, classic_window: NativeWindow
) -> None:
    hours = grid(classic_window)
    classic_window.prev_nav.setFocus(Qt.FocusReason.TabFocusReason)
    hours.setFocus(Qt.FocusReason.MouseFocusReason)
    qapp.processEvents()
    assert classic_window.focusWidget() is hours
    assert not hours.ring_shown


def test_arrow_keys_move_a_quarter_hour_up_and_down_and_a_day_left_and_right(
    qapp: QApplication, classic_window: NativeWindow
) -> None:
    hours = grid(classic_window)
    tab_to_grid(classic_window)
    steps = [
        (Qt.Key.Key_Down, (WEDNESDAY, 14 * 60 + 30)),
        (Qt.Key.Key_Down, (WEDNESDAY, 14 * 60 + 45)),
        (Qt.Key.Key_Up, (WEDNESDAY, 14 * 60 + 30)),
        (Qt.Key.Key_Right, (WEDNESDAY + 1, 14 * 60 + 30)),
        (Qt.Key.Key_Left, (WEDNESDAY, 14 * 60 + 30)),
        (Qt.Key.Key_Left, (WEDNESDAY - 1, 14 * 60 + 30)),
        (Qt.Key.Key_Left, (0, 14 * 60 + 30)),
        (Qt.Key.Key_Left, (0, 14 * 60 + 30)),
    ]
    for which, expected in steps:
        key(classic_window, which)
        assert hours.focus_slot() == expected, f"after {which.name}"


def test_arrows_stop_at_the_ends_of_the_day(qapp: QApplication, classic_window: NativeWindow) -> None:
    hours = grid(classic_window)
    tab_to_grid(classic_window)
    for _ in range(100):
        key(classic_window, Qt.Key.Key_Up)
    assert hours.focus_slot() == (WEDNESDAY, 0)
    for _ in range(100):
        key(classic_window, Qt.Key.Key_Down)
    assert hours.focus_slot() == (WEDNESDAY, 24 * 60 - 15)


def test_an_arrow_onto_a_block_focuses_it_and_enter_opens_it(
    qapp: QApplication, classic_window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    add_piano(qapp, classic_window)
    hours = grid(classic_window)
    opened: list[str] = []

    def look(dialog: BlockDialog) -> int:
        opened.append(dialog.block()["id"])
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(BlockDialog, "exec", look)
    tab_to_grid(classic_window)
    key(classic_window, Qt.Key.Key_Down)
    key(classic_window, Qt.Key.Key_Down)
    assert hours.focus_block() is None, "14:45 is free"
    key(classic_window, Qt.Key.Key_Down)
    assert hours.focus_slot() == (WEDNESDAY, 15 * 60)
    assert hours.focus_block() == ("piano", WEDNESDAY)
    assert hours.focus_rect() is not None, "the ring has a block to go round"
    assert classic_window.session.selected_block_id == "piano"
    key(classic_window, Qt.Key.Key_Down)
    assert hours.focus_block() == ("piano", WEDNESDAY), "15:15 is still Piano"
    key(classic_window, Qt.Key.Key_Return)
    assert opened == ["piano"]
    for _ in range(3):
        key(classic_window, Qt.Key.Key_Up)
    assert hours.focus_block() is None
    assert classic_window.session.selected_block_id is None, (
        "a free slot is not a block that Delete could take"
    )


def test_enter_on_a_free_slot_opens_the_free_time_menu(
    qapp: QApplication, classic_window: NativeWindow, menus: list[dict]
) -> None:
    tab_to_grid(classic_window)
    key(classic_window, Qt.Key.Key_Down)
    key(classic_window, Qt.Key.Key_Return)
    asked = [(shown["name"], shown["rows"][0]) for shown in menus]
    assert asked == [("spotMenu", "Add fixed time at 2:30 PM")]


def test_shift_f10_on_a_block_opens_its_menu(
    qapp: QApplication, classic_window: NativeWindow, menus: list[dict]
) -> None:
    add_piano(qapp, classic_window)
    tab_to_grid(classic_window)
    for _ in range(4):
        key(classic_window, Qt.Key.Key_Down)
    key(classic_window, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier)
    assert [(shown["name"], shown["rows"][0]) for shown in menus] == [("blockMenu", "Open\tEnter")]


def test_delete_takes_away_the_focused_block(qapp: QApplication, classic_window: NativeWindow) -> None:
    add_piano(qapp, classic_window)
    tab_to_grid(classic_window)
    for _ in range(4):
        key(classic_window, Qt.Key.Key_Down)
    key(classic_window, Qt.Key.Key_Delete)
    settled(qapp, classic_window)
    assert not any(block["id"] == "piano" for block in classic_window.session.blocks)


def test_delete_on_a_free_slot_takes_nothing_even_after_a_block_was_chosen(
    qapp: QApplication, classic_window: NativeWindow
) -> None:
    add_piano(qapp, classic_window)
    classic_window.session.select_block("piano", WEDNESDAY)
    tab_to_grid(classic_window)
    key(classic_window, Qt.Key.Key_Delete)
    settled(qapp, classic_window)
    assert any(block["id"] == "piano" for block in classic_window.session.blocks)


def test_escape_leaves_the_grid_for_the_top_bar(qapp: QApplication, classic_window: NativeWindow) -> None:
    tab_to_grid(classic_window)
    key(classic_window, Qt.Key.Key_Escape)
    focus = classic_window.focusWidget()
    assert focus is classic_window.findChild(QAbstractButton, "viewWeek")


def test_no_ring_is_drawn_when_the_grid_is_not_focused(
    qapp: QApplication, classic_window: NativeWindow
) -> None:
    hours = grid(classic_window)
    tab_to_grid(classic_window)
    key(classic_window, Qt.Key.Key_Tab)
    assert not hours.ring_shown


def test_where_time_runs_across_left_and_right_move_the_time_and_up_and_down_the_day(
    qapp: QApplication, classic_window: NativeWindow
) -> None:
    window = classic_window
    window._layout = sanitize_layout({"main": "mission", "day": "one"})
    window._apply_appearance()
    window._on_week()
    settled(qapp, window)
    lanes = [
        hours for hours in window._week_surfaces() if hours.tracks and hours.tracks[0].axis is Axis.ACROSS
    ]
    assert lanes, "Mission shows a lane for each day"
    hours = lanes[0]
    hours.setFocus(Qt.FocusReason.TabFocusReason)
    day, minute = hours.focus_slot()
    key(window, Qt.Key.Key_Right)
    assert hours.focus_slot() == (day, minute + 15)
    key(window, Qt.Key.Key_Down)
    assert hours.focus_slot() == (day + 1, minute + 15)
    key(window, Qt.Key.Key_Left)
    key(window, Qt.Key.Key_Up)
    assert hours.focus_slot() == (day, minute)
