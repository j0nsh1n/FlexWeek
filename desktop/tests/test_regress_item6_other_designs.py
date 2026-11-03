"""Item 6 in the designs that draw their own hours (Timeline, Mission, Bento, Retro and Clay): a press on
the hours moves the keyboard spot and hides the ring, the sheet it opens gives the keyboard back to that
spot, Shift+F10 asks about it, and a saved new block gets the keyboard. The same steps as
test_regress_item6_keyboard_after_sheet.py, which covers Today's app. Clay is not here: it draws one canvas
for each day, and a press on a side card brings that card to the front before it creates anything."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QWidget

from desktop.native.hours.canvas import HoursCanvas
from desktop.native.hours.geometry import Axis
from desktop.native.layouts.registry import sanitize_layout
from desktop.native.weekmodel import clock_text
from desktop.native.widgets import _give_focus_back
from desktop.tests.grid_support import (  # noqa: F401
    grid,
    key,
    menus,
    qapp,
    server,
    settled,
    signed_in,
    signed_out,
    window,
)
from desktop.tests.test_regress_item6_keyboard_after_sheet import (
    MONDAY,
    SCHOOL,
    THURSDAY,
    click_with_sheet,
    escape,
    name_and_save,
)
from desktop.tests.window_support import host, wait_until  # noqa: F401

DESIGNS = ("timeline", "mission", "bento", "retro")


def in_design(qapp, window, design: str) -> HoursCanvas:
    """The window in `design` on Wednesday noon with School saved, and the hours that show Monday and
    Thursday both."""
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
    hours.take_focus(True, ("school", MONDAY, 8 * 60))
    qapp.processEvents()
    assert hours.focus_block() == ("school", MONDAY) and hours.ring_shown
    return hours


@pytest.mark.parametrize("design", DESIGNS)
def test_after_a_click_and_esc_the_spot_is_the_clicked_slot_and_only_it_is_focused(
    qapp, window, menus, design
) -> None:
    hours = in_design(qapp, window, design)
    assert click_with_sheet(qapp, window, hours, THURSDAY, 19 * 60, escape) == ["blockDialog"]
    assert window.focusWidget() is hours, "the keyboard did not come back to the hours"
    assert hours.focus_slot() == (THURSDAY, 19 * 60)
    assert not hours.ring_shown
    assert window.session.selected_block_id is None, "School keeps its outline while the spot is elsewhere"
    key(window, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier)
    asked = [(shown["name"], shown["rows"][0]) for shown in menus]
    assert asked == [("spotMenu", f"Add fixed time at {clock_text(19 * 60)}")], asked


@pytest.mark.parametrize("design", DESIGNS)
def test_a_saved_new_block_gets_the_keyboard(qapp, window, design) -> None:
    hours = in_design(qapp, window, design)
    assert click_with_sheet(qapp, window, hours, THURSDAY, 19 * 60, name_and_save) == ["blockDialog"]
    settled(qapp, window)
    club = next((b for b in window.session.blocks if b["title"] == "Club"), None)
    assert club is not None, "the new block was not saved"
    shown = window.planner.currentWidget().hours_surfaces()
    spot = [s.focus_block() for s in shown if s.hasFocus()]
    assert spot == [(club["id"], THURSDAY)], spot


def _hours_waiting_to_be_shown(qapp, host: QWidget) -> tuple[QWidget, QWidget]:
    """Hours that owned the keyboard, then left the window the way Bento re-lays tiles."""
    hours = QWidget(host)
    hours.setObjectName("hoursCanvas")
    hours.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    hours.show()
    hours.setFocus()
    qapp.processEvents()
    assert hours.hasFocus()
    holder = QWidget()
    hours.hide()
    hours.setParent(holder)
    qapp.processEvents()
    _give_focus_back(hours)
    return hours, holder


def test_hours_get_the_keyboard_back_if_they_were_hidden_while_the_sheet_closed(qapp) -> None:
    """Bento takes reused hours out of the grid and hides them while it re-lays tiles. The sheet's
    return can land in that gap, after the hours have left the window."""
    window = QWidget()
    window.resize(200, 120)
    window.show()
    window.activateWindow()
    qapp.processEvents()
    hours, holder = _hours_waiting_to_be_shown(qapp, window)
    hours.setParent(window)
    hours.show()
    qapp.processEvents()
    assert hours.hasFocus()
    holder.deleteLater()
    window.deleteLater()
    qapp.processEvents()


def test_hidden_hours_do_not_take_the_keyboard_from_another_active_window(qapp, monkeypatch) -> None:
    window = QWidget()
    window.resize(200, 120)
    window.show()
    window.activateWindow()
    qapp.processEvents()
    hours, holder = _hours_waiting_to_be_shown(qapp, window)
    other = QWidget()
    other.resize(160, 80)
    other.show()
    box = QWidget(other)
    box.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    other.activateWindow()
    box.setFocus()
    qapp.processEvents()
    assert QApplication.activeWindow() is other
    activations = []
    monkeypatch.setattr(window, "activateWindow", lambda: activations.append(True))
    hours.setParent(window)
    hours.show()
    qapp.processEvents()
    assert QApplication.activeWindow() is other
    assert activations == []
    assert not hours.hasFocus()
    holder.deleteLater()
    other.deleteLater()
    window.deleteLater()
    qapp.processEvents()


def test_hidden_hours_do_not_take_the_keyboard_from_another_field_or_page(qapp) -> None:
    host = QWidget()
    host.resize(320, 200)
    host.show()
    host.activateWindow()
    week = QWidget(host)
    page = QWidget(host)
    week.setGeometry(0, 0, 320, 90)
    page.setGeometry(0, 100, 320, 90)
    week.show()
    page.show()
    qapp.processEvents()
    hours, holder = _hours_waiting_to_be_shown(qapp, week)
    field = QLineEdit(page)
    field.show()
    host.activateWindow()
    field.setFocus()
    qapp.processEvents()
    assert field.hasFocus()
    hours.setParent(week)
    hours.show()
    qapp.processEvents()
    assert field.hasFocus()
    assert not hours.hasFocus()
    holder.deleteLater()
    host.deleteLater()
    qapp.processEvents()


def test_hidden_hours_do_not_take_the_keyboard_from_an_open_modal(qapp) -> None:
    host = QWidget()
    host.resize(320, 180)
    host.show()
    host.activateWindow()
    qapp.processEvents()
    hours, holder = _hours_waiting_to_be_shown(qapp, host)
    dialog = QDialog(host)
    dialog.setModal(True)
    edit = QLineEdit(dialog)
    dialog.resize(200, 80)
    dialog.show()
    edit.setFocus()
    qapp.processEvents()
    assert QApplication.activeModalWidget() is dialog
    assert edit.hasFocus()
    hours.setParent(host)
    hours.show()
    qapp.processEvents()
    assert QApplication.activeModalWidget() is dialog
    assert edit.hasFocus()
    assert not hours.hasFocus()
    dialog.close()
    holder.deleteLater()
    host.deleteLater()
    qapp.processEvents()


def test_a_background_refresh_keeps_bentos_keyboard_spot_when_the_app_returns(qapp, window, host) -> None:
    hours = in_design(qapp, window, "bento")
    host.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    host.show()
    host.activateWindow()
    host.setFocus()
    wait_until(qapp, host.hasFocus)
    assert window.focusWidget() is hours

    view = window.planner.currentWidget()
    scene = view.scene
    assert scene is not None
    view.show_week(replace(scene, minute=scene.minute + 1))
    assert host.hasFocus(), "a background refresh took the keyboard from another window"

    window.activateWindow()
    wait_until(qapp, window.isActiveWindow)
    spot = [surface.focus_block() for surface in view.hours_surfaces() if surface.hasFocus()]
    assert spot == [("school", MONDAY)], spot


@pytest.mark.parametrize("design", DESIGNS)
def test_clicking_school_then_closing_its_sheet_moves_right_from_school(qapp, window, design) -> None:
    hours = in_design(qapp, window, design)
    hours.take_focus(True, ("school", MONDAY, 8 * 60))
    click_with_sheet(qapp, window, hours, MONDAY, 10 * 60, escape)
    # Where time runs across, the days are up and down.
    across = hours.track_for(MONDAY).axis is Axis.ACROSS
    key(window, Qt.Key.Key_Down if across else Qt.Key.Key_Right)
    assert hours.focus_slot()[0] == MONDAY + 1
    assert hours.focus_block() == ("school", MONDAY + 1)
