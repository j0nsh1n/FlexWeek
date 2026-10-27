"""The week list remains reachable in every design without moving the grid."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractScrollArea, QApplication, QWidget

from desktop.native.layouts.registry import sanitize_layout
from desktop.tests.window_support import qapp, server, settled, signed_out, window  # noqa: F401

DESIGNS = ("classic", "retro", "clay", "bento", "mission", "timeline")
SCHOOL = {"id": "school", "title": "School", "kind": "locked", "category": "class", "start": "08:30",
          "duration_min": 405, "days": [0, 1, 2, 3, 4]}
CTRL_SHIFT = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier


def in_design(qapp, window, design: str) -> QWidget:
    window.session.add_block(dict(SCHOOL))
    window.session.save()
    settled(qapp, window)
    window._layout = sanitize_layout({"main": design, "day": "one"})
    window._apply_appearance()
    window._on_week()
    settled(qapp, window)
    surfaces = [s for s in window.planner.currentWidget().hours_surfaces() if s.isVisible()]
    assert surfaces, f"{design} shows no hours"
    return surfaces[0]


def key(window, k, mods=Qt.KeyboardModifier.NoModifier) -> None:
    QTest.keyClick(window.windowHandle(), k, mods)
    for _ in range(3):
        QApplication.processEvents()


@pytest.mark.parametrize("design", DESIGNS)
def test_0k_every_main_design_has_the_week_list_before_its_hours(qapp, window, design) -> None:
    hours = in_design(qapp, window, design)
    listing = window.week_access_list
    window._sync_more_menu()
    action = next(action for action, button in window._more_pairs if button is window.week_list_row)
    assert action.isEnabled() and action.text() == "Week as a list", f"{design}: no way into the week list"
    key(window, Qt.Key.Key_L, CTRL_SHIFT)
    assert listing.isVisibleTo(window), f"{design}: no week list"
    assert any("School" in listing.item(i).text() for i in range(listing.count()))
    cursor, seen = listing.nextInFocusChain(), []
    while cursor is not listing and cursor not in seen and cursor is not hours:
        seen.append(cursor)
        cursor = cursor.nextInFocusChain()
    assert cursor is hours, f"{design}: the hours are not after the list in Tab order"


@pytest.mark.parametrize("design", DESIGNS)
def test_0k_ctrl_shift_l_from_the_hours_opens_the_list_and_enter_opens_a_block(
    qapp, window, monkeypatch, design
) -> None:
    hours = in_design(qapp, window, design)
    hours.setFocus(Qt.FocusReason.OtherFocusReason)
    QApplication.processEvents()
    key(window, Qt.Key.Key_L, CTRL_SHIFT)
    listing = window.week_access_list
    assert QApplication.focusWidget() is listing, f"{design}: focus on {QApplication.focusWidget()}"
    row = next(i for i in range(listing.count())
               if (listing.item(i).data(Qt.ItemDataRole.UserRole) or (None,))[0] == "school")
    listing.setCurrentRow(row)
    opened: list[str] = []
    monkeypatch.setattr(window, "_edit_block", opened.append)
    key(window, Qt.Key.Key_Return)
    assert opened == ["school"]


@pytest.mark.parametrize("design", ["classic", "timeline"])
def test_u19_tabbing_through_the_week_page_twice_never_moves_the_hours(qapp, window, design) -> None:
    hours = in_design(qapp, window, design)
    listing = window.week_access_list
    before = listing.previousInFocusChain()
    before.setFocus(Qt.FocusReason.TabFocusReason)
    QApplication.processEvents()
    # The hours scroll inside their area to the keyboard spot; the area itself must not move.
    area = hours.parentWidget()
    while area is not None and not isinstance(area, QAbstractScrollArea):
        area = area.parentWidget()
    frame = area or hours
    tops = {frame.mapTo(window, QPoint(0, 0)).y()}
    for _ in range(2 * 12):  # two passes over the list, the hours and what follows
        key(window, Qt.Key.Key_Tab)
        tops.add(frame.mapTo(window, QPoint(0, 0)).y())
    assert len(tops) == 1, f"the hours sat at y = {sorted(tops)}"


def test_u19_more_is_a_tab_stop_with_a_week_list_entry(qapp, window) -> None:
    in_design(qapp, window, "classic")
    assert window.more_button.isVisible()
    assert window.more_button.focusPolicy() & Qt.FocusPolicy.TabFocus
    window._sync_more_menu()
    action = next(action for action, button in window._more_pairs if button is window.week_list_row)
    assert action.isEnabled() and "Ctrl+Shift+L" in action.toolTip()


def test_u19_esc_in_the_list_returns_to_the_grid(qapp, window) -> None:
    hours = in_design(qapp, window, "classic")
    hours.setFocus(Qt.FocusReason.OtherFocusReason)
    key(window, Qt.Key.Key_L, CTRL_SHIFT)
    assert QApplication.focusWidget() is window.week_access_list
    key(window, Qt.Key.Key_Escape)
    assert QApplication.focusWidget() is hours, f"focus on {QApplication.focusWidget()}"
