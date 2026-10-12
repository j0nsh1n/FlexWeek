"""U19: the keyboard week list never makes the week jump. A fixed 28 px "Week as a list · Ctrl+Shift+L"
row above the grid is the Tab stop; Enter or Space on it, or Ctrl+Shift+L, opens the list over the grid with
the keyboard on its first row; Esc closes it and puts the keyboard back where it was.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QStyle, QStyleOptionButton

from desktop.native.layouts.base import NARROW_WIDTH
from desktop.native.layouts.registry import LAYOUTS
from desktop.native.look import LOOK_PRESETS
from desktop.tests.window_support import qapp, server, settled, signed_out, window  # noqa: F401

CTRL_SHIFT = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
ROW_NAME = "Week as a list · Ctrl+Shift+L"


def key(window, k, mods=Qt.KeyboardModifier.NoModifier) -> None:
    QTest.keyClick(window.windowHandle(), k, mods)
    for _ in range(3):
        QApplication.processEvents()


def with_school(qapp, window) -> None:
    window.session.add_block({"id": "school", "title": "School", "kind": "locked", "category": "class",
                              "start": "08:30", "duration_min": 405, "days": [0, 1, 2, 3, 4]})
    settled(qapp, window)


def grid_top(window) -> int:
    return window.planner.mapTo(window, QPoint(0, 0)).y()


def test_u19_the_row_is_always_there_28_px_with_its_name_and_a_tab_stop(qapp, window) -> None:
    with_school(qapp, window)
    row = window.week_list_row
    assert row.isVisible() and row.height() == 28
    assert row.accessibleName() == ROW_NAME and row.text() == ROW_NAME
    assert row.focusPolicy() & Qt.FocusPolicy.TabFocus
    assert not window.week_list_panel.isVisible()


# Every design on the default look, and every look on Today's app, as the roomy-button tests do.
CLIP_COMBOS = [(design, "default") for design in LAYOUTS] + [
    ("classic", preset) for preset in LOOK_PRESETS if preset != "default"
]


@pytest.mark.parametrize("size", ["small", "normal", "large"])
@pytest.mark.parametrize(("design", "preset"), CLIP_COMBOS)
def test_u19_the_row_is_28_px_32_at_large_and_its_words_get_the_full_height_the_font_needs(
    qapp, window, design, preset, size
) -> None:
    window.resize(1280, 860)
    window._layout = {"main": design, "day": "one", "options": {}}
    window._look = {"preset": preset, "knobs": {"text": size}}
    window.session.look = window._look
    window._apply_appearance()
    settled(qapp, window)
    row = window.week_list_row
    option = QStyleOptionButton()
    row.initStyleOption(option)
    contents = row.style().subElementRect(QStyle.SubElement.SE_PushButtonContents, option, row)
    expected = {"small": 28, "normal": 28, "large": 32}[size]
    assert row.height() == expected, f"{design}/{preset}/{size}: row is {row.height()} px, not {expected}"
    assert contents.height() >= row.fontMetrics().height(), (
        f"{design}/{preset}/{size}: words box {contents.height()} px, font needs {row.fontMetrics().height()}"
    )


def test_u19_the_row_comes_before_the_grid_in_tab_order_and_in_the_layout(qapp, window) -> None:
    with_school(qapp, window)
    row, canvas = window.week_list_row, window.week_table.hours
    cursor, seen = row.nextInFocusChain(), []
    while cursor is not row and cursor not in seen and cursor is not canvas:
        seen.append(cursor)
        cursor = cursor.nextInFocusChain()
    assert cursor is canvas, "the grid is not after the row in Tab order"
    assert row.mapTo(window, QPoint(0, 0)).y() + row.height() <= grid_top(window)


def test_u19_tabbing_through_the_week_page_twice_never_moves_the_grid(qapp, window) -> None:
    with_school(qapp, window)
    window.week_list_row.setFocus(Qt.FocusReason.OtherFocusReason)
    QApplication.processEvents()
    tops = {grid_top(window)}
    row_tops = {window.week_list_row.y()}
    for _ in range(2 * 14):
        key(window, Qt.Key.Key_Tab)
        tops.add(grid_top(window))
        row_tops.add(window.week_list_row.y())
        assert window.week_list_row.height() == 28
    assert len(tops) == 1, f"the grid sat at y = {sorted(tops)}"
    assert len(row_tops) == 1


def test_u19_opening_and_closing_the_list_never_moves_the_grid(qapp, window) -> None:
    with_school(qapp, window)
    before = grid_top(window)
    window.week_table.hours.setFocus(Qt.FocusReason.OtherFocusReason)
    key(window, Qt.Key.Key_L, CTRL_SHIFT)
    settled(qapp, window)
    assert window.week_list_panel.isVisible() and grid_top(window) == before
    key(window, Qt.Key.Key_Escape)
    settled(qapp, window)
    assert not window.week_list_panel.isVisible() and grid_top(window) == before


@pytest.mark.parametrize("opener", [Qt.Key.Key_Return, Qt.Key.Key_Space])
def test_u19_enter_or_space_on_the_row_opens_the_list_on_its_first_row_and_esc_returns(
    qapp, window, opener
) -> None:
    with_school(qapp, window)
    window.week_list_row.setFocus(Qt.FocusReason.TabFocusReason)
    QApplication.processEvents()
    key(window, opener)
    listing = window.week_access_list
    assert window.week_list_panel.isVisible() and listing.isVisibleTo(window)
    assert QApplication.focusWidget() is listing and listing.currentRow() == 0
    key(window, Qt.Key.Key_Escape)
    assert not window.week_list_panel.isVisible()
    assert QApplication.focusWidget() is window.week_list_row


def test_u19_ctrl_shift_l_from_the_top_bar_opens_the_list_and_esc_goes_back_to_the_top_bar(
    qapp, window
) -> None:
    with_school(qapp, window)
    bar = window.settings_gear
    assert isinstance(bar, QPushButton) and bar.isVisible()
    bar.setFocus(Qt.FocusReason.OtherFocusReason)
    QApplication.processEvents()
    key(window, Qt.Key.Key_L, CTRL_SHIFT)
    assert QApplication.focusWidget() is window.week_access_list
    assert window.week_access_list.currentRow() == 0
    key(window, Qt.Key.Key_Escape)
    assert QApplication.focusWidget() is bar


def test_u19_ctrl_shift_l_from_the_grid_opens_the_list_and_esc_returns_to_the_grid(qapp, window) -> None:
    with_school(qapp, window)
    grid = window.week_table.hours
    grid.setFocus(Qt.FocusReason.OtherFocusReason)
    QApplication.processEvents()
    key(window, Qt.Key.Key_L, CTRL_SHIFT)
    assert QApplication.focusWidget() is window.week_access_list
    key(window, Qt.Key.Key_Escape)
    assert QApplication.focusWidget() is grid and not window.week_list_panel.isVisible()


def test_u19_enter_on_a_row_opens_that_block_and_the_menu_key_still_opens_its_menu(
    qapp, window, monkeypatch
) -> None:
    with_school(qapp, window)
    key(window, Qt.Key.Key_L, CTRL_SHIFT)
    listing = window.week_access_list
    row = next(i for i in range(listing.count())
               if (listing.item(i).data(Qt.ItemDataRole.UserRole) or (None,))[0] == "school")
    listing.setCurrentRow(row)
    opened, menus = [], []
    monkeypatch.setattr(window, "_edit_block", opened.append)
    monkeypatch.setattr(window, "_block_menu", lambda block_id, day, point: menus.append((block_id, day)))
    key(window, Qt.Key.Key_Return)
    assert opened == ["school"]
    key(window, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier)
    key(window, Qt.Key.Key_Menu)
    assert menus == [("school", 0), ("school", 0)]


def test_u19_the_list_floats_at_its_width_on_a_wide_window_and_over_the_whole_grid_on_a_narrow_one(
    qapp, window
) -> None:
    with_school(qapp, window)
    window.resize(max(NARROW_WIDTH + 400, 1300), 800)
    settled(qapp, window)
    key(window, Qt.Key.Key_L, CTRL_SHIFT)
    settled(qapp, window)
    panel = window.week_list_panel
    assert panel.width() == 360 and panel.height() == window.planner.height()
    key(window, Qt.Key.Key_Escape)
    window.resize(NARROW_WIDTH - 100, 800)
    settled(qapp, window)
    key(window, Qt.Key.Key_L, CTRL_SHIFT)
    settled(qapp, window)
    assert panel.width() == window.planner.width()
    assert panel.geometry().topLeft() == window.planner.mapTo(window._week_page, QPoint(0, 0))


def test_u19_the_row_and_list_go_away_with_the_week_view(qapp, window) -> None:
    with_school(qapp, window)
    key(window, Qt.Key.Key_L, CTRL_SHIFT)
    assert window.week_list_panel.isVisible()
    window._choose_view("month")
    settled(qapp, window)
    assert not window.week_list_row.isVisible() and not window.week_list_panel.isVisible()
    window._choose_view("week")
    settled(qapp, window)
    assert window.week_list_row.isVisible() and not window.week_list_panel.isVisible()


def test_u19_the_focus_driven_resize_is_gone() -> None:
    from desktop.native import window as module

    assert not hasattr(module, "WEEK_LIST_OPEN") and not hasattr(module, "WEEK_LIST_FOLDED")
