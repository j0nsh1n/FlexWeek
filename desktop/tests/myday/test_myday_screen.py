# ruff: noqa: F811
"""The Material My day screen on the account's own data: its ring and free-time card, the lists it
keeps, the controls a student reaches, and that it stays on today whatever Day, Week or Month browse.

Thursday 17:00: School 08:00-14:30 is over, the History essay waits at 18:45.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_material_day import (  # noqa: E402
    bridge_of,
    pref,
    root_bridge,
    seed_thursday,
)
from desktop.tests.light_app import open_light  # noqa: E402, F401
from desktop.tests.material_support import pump, qml, show_material, visuals  # noqa: E402
from desktop.tests.window_support import qapp, settled  # noqa: E402, F401


@pytest.fixture()
def window(qapp: QApplication, open_light) -> NativeWindow:
    return seed_thursday(qapp, open_light((1280, 800)), hour=17)


def test_the_ring_counts_what_is_left_today(qapp: QApplication, window: NativeWindow) -> None:
    pref(window, clock_24h=True)
    root = show_material(qapp, window)
    myday = root_bridge(root).property("myday")
    assert myday.property("ringCount") == 1
    assert myday.property("ringCaption") == "thing left"
    assert myday.property("ringShare") == pytest.approx(0.5)


def test_start_focus_on_my_day_opens_the_next_homework(qapp: QApplication, window: NativeWindow) -> None:
    root = show_material(qapp, window)
    myday = root_bridge(root).property("myday")
    assert str(myday.property("nowTitle")) == "Free for 1 h 45 min"
    try:
        myday.startFocus()
        pump(qapp)
        focus = window._material_page.bridge.focus
        assert str(focus.property("title")) == "History essay"
        assert str(myday.property("nowTitle")) == "Free for 1 h 45 min"
    finally:
        window.session.reset_focus()
        pump(qapp)


def test_nudges_off_hides_the_free_time_card_on_my_day(qapp: QApplication, window: NativeWindow) -> None:
    pref(window, free_time_nudges=False)
    root = show_material(qapp, window)
    assert root_bridge(root).property("myday").property("showNow") is False
    pref(window, free_time_nudges=True)
    root = show_material(qapp, window)
    assert root_bridge(root).property("myday").property("showNow") is True


def test_my_day_keeps_its_up_next_and_done_lists(qapp: QApplication, window: NativeWindow) -> None:
    root = show_material(qapp, window)
    bridge_of(window).showPage("myday")
    pump(qapp)
    my_names = {str(item.objectName()) for item in visuals(qml(root, "materialMyDay"))}
    assert "myDayUpNext" in my_names
    assert "myDayDone" in my_names


def test_the_my_day_screen_has_the_named_controls(qapp: QApplication, window: NativeWindow) -> None:
    root = show_material(qapp, window)
    bridge_of(window).showPage("myday")
    pump(qapp)
    names = {str(item.objectName()) for item in visuals(root)}
    for name in ("materialMyDay", "myDayRing", "myDayNow", "myDayStartFocus", "myDayCount"):
        assert name in names, name


def test_my_day_stays_on_today_while_day_browses_another_date(
    qapp: QApplication, window: NativeWindow
) -> None:
    session = window.session
    bridge = root_bridge(show_material(qapp, window))
    day = bridge.property("day")
    friday = date.fromisoformat(session.selected_day) + timedelta(days=1)
    day.pickDay(friday.day)
    settled(qapp, window)
    pump(qapp)
    assert session.selected_day == friday.isoformat()
    assert bridge.property("myday").property("leftLine") == "1 thing left today"


def test_my_day_keeps_today_after_browsing_another_week(qapp: QApplication, window: NativeWindow) -> None:
    root = show_material(qapp, window)
    bridge = root_bridge(root)
    session = window.session
    current = session.week_start
    next_week = (date.fromisoformat(current) + timedelta(days=7)).isoformat()
    past_week = (date.fromisoformat(current) + timedelta(days=-7)).isoformat()
    bridge.showPage("myday")
    settled(qapp, window)
    pump(qapp)
    myday = bridge.property("myday")
    initial = myday.property("upNext").rowCount()
    assert initial > 0
    assert myday.property("waiting") is False
    bridge.showPage("week")
    session.load_week(next_week)
    settled(qapp, window)
    bridge.showPage("myday")
    settled(qapp, window)
    pump(qapp)
    assert myday.property("waiting") is False
    assert myday.property("loadError") == ""
    assert myday.property("upNext").rowCount() == initial
    session.load_week(past_week)
    settled(qapp, window)
    settled(qapp, window)
    pump(qapp)
    assert myday.property("upNext").rowCount() == initial
    future = (date.fromisoformat(current) + timedelta(days=21)).isoformat()
    session.open_day(future)
    settled(qapp, window)
    bridge.showPage("myday")
    settled(qapp, window)
    pump(qapp)
    assert myday.property("upNext").rowCount() == initial
    bridge.showPage("month")
    settled(qapp, window)
    session.shift_month(1)
    settled(qapp, window)
    bridge.showPage("myday")
    settled(qapp, window)
    pump(qapp)
    assert myday.property("upNext").rowCount() == initial
