# ruff: noqa: F811
"""The Material Day screen on the account's own data: the count line and the free-time card, the
clock setting, the free-time nudge preference, picking a date, and the controls a student reaches.

Expected strings come from the spec (Jonathan's words) and from the clock set in the fixture (Thursday
17:00: School 08:00-14:30 is over, the History essay waits at 18:45), not from reading the code's output.
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
    rows_of,
    seed_thursday,
)
from desktop.tests.light_app import open_light  # noqa: E402, F401
from desktop.tests.material_support import pump, show_material, visuals  # noqa: E402
from desktop.tests.window_support import qapp, settled  # noqa: E402, F401


@pytest.fixture()
def window(qapp: QApplication, open_light) -> NativeWindow:
    return seed_thursday(qapp, open_light((1280, 800)), hour=17)


def test_the_day_screen_reads_the_real_day(qapp: QApplication, window: NativeWindow) -> None:
    session = window.session
    prefs = dict(session.preferences or {})
    prefs["clock_24h"] = True
    prefs.pop("free_time_nudges", None)
    prefs.pop("nudges", None)
    session.preferences = prefs
    root = show_material(qapp, window)
    day = root_bridge(root).property("day")
    assert day.property("leftLine") == "1 thing left today"
    assert day.property("showNow") is True
    assert day.property("nowTitle") == "Free for 1 h 45 min"
    assert day.property("nowMinutes") == 105
    assert day.property("nowLine") == "Next: History essay at 18:45"
    up = rows_of(day.property("upNext"))
    done = rows_of(day.property("doneRows"))
    assert [row["title"] for row in up] == ["History essay"]
    assert up[0]["subtitle"].startswith("18:45–19:45")
    assert up[0]["canFinish"] is True
    assert [row["title"] for row in done] == ["School"]
    assert done[0]["subtitle"] == "08:00–14:30"


def test_start_focus_on_the_day_screen_opens_the_next_homework(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = show_material(qapp, window)
    day = root_bridge(root).property("day")
    try:
        day.startFocus()
        pump(qapp)
        focus = window._material_page.bridge.focus
        assert str(focus.property("title")) == "History essay"
        assert str(day.property("nowTitle")) == "Free for 1 h 45 min"
    finally:
        window.session.reset_focus()
        # The Focus screen this opened would otherwise stay up.
        window._material_page.bridge.focus.hide()
        pump(qapp)


def test_the_clock_setting_changes_the_row_times(qapp: QApplication, window: NativeWindow) -> None:
    pref(window, clock_24h=False)
    root = show_material(qapp, window)
    day = root_bridge(root).property("day")
    done = rows_of(day.property("doneRows"))
    assert done[0]["subtitle"] == "8 AM–2:30 PM"


def test_nudges_off_hides_the_free_time_card_on_day(qapp: QApplication, window: NativeWindow) -> None:
    pref(window, free_time_nudges=False)
    root = show_material(qapp, window)
    assert root_bridge(root).property("day").property("showNow") is False
    pref(window, free_time_nudges=True)
    root = show_material(qapp, window)
    assert root_bridge(root).property("day").property("showNow") is True


def test_picking_a_date_shows_that_day(qapp: QApplication, window: NativeWindow) -> None:
    session = window.session
    root = show_material(qapp, window)
    day = root_bridge(root).property("day")
    thursday = date.fromisoformat(session.selected_day)
    friday = thursday + timedelta(days=1)
    assert day.property("miniDay") == thursday.day
    day.pickDay(friday.day)
    settled(qapp, window)
    pump(qapp)
    assert session.selected_day == friday.isoformat()
    assert day.property("miniDay") == friday.day
    assert day.property("leftLine") == "1 thing left"
    assert [row["title"] for row in rows_of(day.property("upNext"))] == ["School"]
    assert day.property("showNow") is False
    day.previousDay()
    settled(qapp, window)
    pump(qapp)
    assert session.selected_day == thursday.isoformat()
    assert day.property("leftLine") == "1 thing left today"
    day.nextDay()
    settled(qapp, window)
    pump(qapp)
    assert session.selected_day == friday.isoformat()
    day.pickDay(thursday.day)
    settled(qapp, window)
    assert session.selected_day == thursday.isoformat()


def test_the_day_screen_has_the_named_controls(qapp: QApplication, window: NativeWindow) -> None:
    root = show_material(qapp, window)
    bridge_of(window).showPage("day")
    pump(qapp)
    names = {str(item.objectName()) for item in visuals(root)}
    for name in (
        "materialDay",
        "dayPrevious",
        "dayNext",
        "dayLeftLine",
        "dayNow",
        "dayNowTitle",
        "dayStartFocus",
        "dayMonthToggle",
        "dayMonthSide",
        "dayMiniMonth",
        "dayNowLabel",
        "dayScroller",
    ):
        assert name in names, name
