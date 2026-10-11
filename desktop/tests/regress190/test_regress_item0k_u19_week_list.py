"""Regression for item 0k in every main design (fix-specs.md batch 12: "Every main design that shows a week
has the list", before the grid in Tab order, Ctrl+Shift+L, Enter opens a block) and QA's U19
(fix-specs-0190.md: the list must not make the week jump; a fixed 28 px "Week as a list · Ctrl+Shift+L"
row; Esc returns to the grid).

Note: 0.19.0's own test_0k_the_week_list_takes_no_room_until_the_keyboard_reaches_it asserts the
focus-driven resize that U19 removes; it will need changing with the U19 fix.
Known failures are xfail(strict=True).
"""

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
KNOWN_JUMP = "known failure (U19): the list grows 132 px on FocusIn and folds on FocusOut, moving the grid"
KNOWN_ROW = "known failure (U19.1): there is no fixed 'Week as a list · Ctrl+Shift+L' row above the grid"
KNOWN_ESC = "known failure (U19.2): Esc in the week list does not return the keyboard to the grid"


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
    assert window.week_list_row.isVisibleTo(window), f"{design}: no way into the week list"
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


def test_u19_a_fixed_28_px_week_as_a_list_row_is_a_tab_stop(qapp, window) -> None:
    in_design(qapp, window, "classic")
    rows = [w for w in window.findChildren(QWidget)
            if w.isVisible() and "week as a list" in w.accessibleName().lower()
            and "ctrl+shift+l" in w.accessibleName().lower()]
    assert rows, "no 'Week as a list · Ctrl+Shift+L' row"
    assert rows[0].height() == 28 and rows[0].focusPolicy() & Qt.FocusPolicy.TabFocus


def test_u19_esc_in_the_list_returns_to_the_grid(qapp, window) -> None:
    hours = in_design(qapp, window, "classic")
    hours.setFocus(Qt.FocusReason.OtherFocusReason)
    key(window, Qt.Key.Key_L, CTRL_SHIFT)
    assert QApplication.focusWidget() is window.week_access_list
    key(window, Qt.Key.Key_Escape)
    assert QApplication.focusWidget() is hours, f"focus on {QApplication.focusWidget()}"
