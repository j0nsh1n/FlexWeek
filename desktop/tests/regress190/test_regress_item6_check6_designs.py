"""Regression for item 6, acceptance check 6 (fix-specs.md batch 12): checks 1-4 repeated in Timeline,
Mission, Bento and Retro, which draw their own hours. Written from our 0.18.4 item 6 tests (real clicks
and keys through the window system); 0.19.0's own test_regress_item6_other_designs.py covers 1-3 with
take_focus, and this adds Enter on the saved block (check 2) and the one-outline rule (check 4).
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from desktop.native.hours.geometry import Axis
from desktop.native.layouts.registry import sanitize_layout
from desktop.native.weekmodel import clock_text
from desktop.native.widgets import BlockDialog
from desktop.tests.grid_support import (  # noqa: F401
    key,
    menus,
    qapp,
    server,
    settled,
    signed_in,
    signed_out,
    window,
)
from desktop.tests.regress184.test_regress_item6_keyboard_after_sheet import (
    MONDAY,
    SCHOOL,
    THURSDAY,
    click_with_sheet,
    escape,
    name_and_save,
)

DESIGNS = ("timeline", "mission", "bento", "retro")


def in_design(qapp, window, design: str):
    noon = datetime.fromisoformat(window.session.week_start) + timedelta(days=2, hours=12)
    window.session.now_ms = lambda: int(noon.timestamp() * 1000)
    window.session.add_block(dict(SCHOOL))
    window.session.save()
    settled(qapp, window)
    window._layout = sanitize_layout({"main": design, "day": "one"})
    window._apply_appearance()
    window._on_week()
    settled(qapp, window)
    shown = window.planner.currentWidget().hours_surfaces()
    both = [s for s in shown if s.track_for(MONDAY, 9 * 60) and s.track_for(THURSDAY, 19 * 60)]
    assert both, f"{design} shows no hours with Monday and Thursday"
    hours = both[0]
    hours.setFocus(Qt.FocusReason.TabFocusReason)
    hours.take_focus(True, ("school", MONDAY, 8 * 60))
    qapp.processEvents()
    assert hours.focus_block() == ("school", MONDAY) and hours.ring_shown
    return hours


@pytest.mark.parametrize("design", DESIGNS)
def test_6_6_check1_click_esc_then_shift_f10_asks_about_the_clicked_slot(qapp, window, menus, design) -> None:
    hours = in_design(qapp, window, design)
    assert click_with_sheet(qapp, window, hours, THURSDAY, 19 * 60, escape) == ["blockDialog"]
    assert window.focusWidget() is hours
    key(window, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier)
    asked = [(shown["name"], shown["rows"][0]) for shown in menus]
    assert asked == [("spotMenu", f"Add fixed time at {clock_text(19 * 60)}")], asked


@pytest.mark.parametrize("design", DESIGNS)
def test_6_6_check2_a_saved_new_block_gets_the_keyboard_and_enter_opens_it(
    qapp, window, monkeypatch, design
) -> None:
    hours = in_design(qapp, window, design)
    assert click_with_sheet(qapp, window, hours, THURSDAY, 19 * 60, name_and_save) == ["blockDialog"]
    settled(qapp, window)
    club = next((b for b in window.session.blocks if b["title"] == "Club"), None)
    assert club is not None, "the new block was not saved"
    focused = [s for s in window.planner.currentWidget().hours_surfaces() if s.hasFocus()]
    assert [s.focus_block() for s in focused] == [(club["id"], THURSDAY)]
    opened: list[str] = []

    def look(dialog: BlockDialog) -> int:
        opened.append(dialog.block()["id"])
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(BlockDialog, "exec", look)
    key(window, Qt.Key.Key_Return)
    assert opened == [club["id"]]


@pytest.mark.parametrize("design", DESIGNS)
def test_6_6_check3_click_school_close_then_the_next_day_key_moves_from_school(qapp, window, design) -> None:
    hours = in_design(qapp, window, design)
    hours.take_focus(True, None)  # the spot somewhere else first
    click_with_sheet(qapp, window, hours, MONDAY, 10 * 60, escape)
    across = hours.track_for(MONDAY).axis is Axis.ACROSS
    key(window, Qt.Key.Key_Down if across else Qt.Key.Key_Right)
    assert hours.focus_slot()[0] == MONDAY + 1 and hours.focus_block() == ("school", MONDAY + 1)


@pytest.mark.parametrize("design", DESIGNS)
def test_6_6_check4_only_one_thing_looks_focused(qapp, window, design) -> None:
    hours = in_design(qapp, window, design)
    click_with_sheet(qapp, window, hours, THURSDAY, 19 * 60, escape)
    spot = hours.focus_block()
    selected = window.session.selected_block_id
    assert selected in (None, spot and spot[0]) and selected != "school", (selected, spot, hours.focus_slot())
    assert not hours.ring_shown, "the ring shows after a mouse click"
