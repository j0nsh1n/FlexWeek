# ruff: noqa: F811
"""Tests for FIX-SPEC PR 5a item F:
Material Day opens on the app's real today from the rail/bottom bar,
opening Day from a Month date still shows that date,
and a 4:00-5:30 PM block is coming up at 3:40 PM, not done.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.test_layouts_window import settled
from desktop.tests.test_material_day import SOCCER, _block, _board
from desktop.tests.test_material_window import _pump, _show_material, qapp, window  # noqa: F401

TODAY = date(2026, 11, 5)


def _bridge(root: QObject) -> QObject:
    return root.property("bridge")


def test_day_from_the_rail_opens_on_today_after_another_day_was_picked(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _show_material(qapp, window)
    bridge = _bridge(root)
    session = window.session
    current = session.week_start
    today_iso = datetime.fromtimestamp(session.now_ms() / 1000).date().isoformat()
    try:
        # First ensure we are on Day view
        bridge.showPage("day")
        settled(qapp, window)
        _pump(qapp)
        day = bridge.property("day")
        assert day.property("iso") == today_iso

        # Browse / pick another day in Day view
        another_day = (date.fromisoformat(today_iso) + timedelta(days=2)).isoformat()
        session.open_day(another_day)
        settled(qapp, window)
        _pump(qapp)
        assert day.property("iso") == another_day

        # Leave Day to Week
        bridge.showPage("week")
        settled(qapp, window)
        _pump(qapp)
        assert bridge.property("screen") == "week"

        # Reopen Day from the rail/bottom bar
        bridge.showPage("day")
        settled(qapp, window)
        _pump(qapp)
        # It must open on the app's real today
        assert day.property("iso") == today_iso
    finally:
        session.load_week(current)
        settled(qapp, window)
        window._use_widgets_styles()


def test_day_from_a_month_date_opens_on_that_date(qapp: QApplication, window: NativeWindow) -> None:
    root = _show_material(qapp, window)
    bridge = _bridge(root)
    session = window.session
    current = session.week_start
    target_date = "2026-11-20"
    try:
        bridge.showPage("month")
        settled(qapp, window)
        _pump(qapp)
        month = bridge.property("month")
        month.selectDate(target_date)
        _pump(qapp)

        # Open Day from that Month date
        month.openDay()
        settled(qapp, window)
        _pump(qapp)

        day = bridge.property("day")
        assert bridge.property("screen") == "day"
        assert day.property("iso") == target_date
    finally:
        session.load_week(current)
        settled(qapp, window)
        window._use_widgets_styles()


def test_a_4pm_to_530pm_block_is_coming_up_at_340pm_not_done() -> None:
    # Soccer is 16:00 to 17:30 (4:00 PM to 5:30 PM)
    soccer = _block("Soccer", *SOCCER, category="exercise")
    # At 3:40 PM (15:40 = 15 * 60 + 40 = 940 min)
    at_340pm = 15 * 60 + 40
    board_340 = _board([soccer], minute=at_340pm, when="today")
    assert [row.title for row in board_340.up_next] == ["Soccer"]
    assert [row.title for row in board_340.done] == []

    # After 17:30 (e.g. 17:35 = 17 * 60 + 35 = 1055 min), it moves to Done
    at_535pm = 17 * 60 + 35
    board_535 = _board([soccer], minute=at_535pm, when="today")
    assert [row.title for row in board_535.up_next] == []
    assert [row.title for row in board_535.done] == ["Soccer"]
