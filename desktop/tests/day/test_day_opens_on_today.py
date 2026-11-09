# ruff: noqa: F811
"""Which date the Material Day screen opens on: today from the rail or bottom bar, however the
student wandered off, and the date they picked in Month when they come from there."""

from __future__ import annotations

import os
from datetime import date, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from backend.tests.fake_clock import CLOCK  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_material_day import root_bridge, seed_thursday  # noqa: E402
from desktop.tests.light_app import open_light  # noqa: E402, F401
from desktop.tests.material_support import pump, show_material  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.window_support import qapp, settled  # noqa: E402, F401


@pytest.fixture()
def window(qapp: QApplication, open_light) -> NativeWindow:
    return seed_thursday(qapp, open_light((1280, 800)), hour=17)


def test_day_from_the_rail_opens_on_today_after_another_day_was_picked(
    qapp: QApplication, window: NativeWindow
) -> None:
    bridge = root_bridge(show_material(qapp, window))
    session = window.session
    today_iso = CLOCK.today().isoformat()
    bridge.showPage("day")
    settled(qapp, window)
    pump(qapp)
    day = bridge.property("day")
    assert day.property("iso") == today_iso

    another_day = (date.fromisoformat(today_iso) + timedelta(days=2)).isoformat()
    session.open_day(another_day)
    settled(qapp, window)
    pump(qapp)
    assert day.property("iso") == another_day

    bridge.showPage("week")
    settled(qapp, window)
    pump(qapp)
    assert bridge.property("screen") == "week"

    bridge.showPage("day")
    settled(qapp, window)
    pump(qapp)
    assert day.property("iso") == today_iso


def test_day_from_a_month_date_opens_on_that_date(qapp: QApplication, window: NativeWindow) -> None:
    bridge = root_bridge(show_material(qapp, window))
    target_date = "2026-11-20"
    bridge.showPage("month")
    settled(qapp, window)
    pump(qapp)
    month = bridge.property("month")
    month.selectDate(target_date)
    pump(qapp)

    month.openDay()
    settled(qapp, window)
    pump(qapp)

    day = bridge.property("day")
    assert bridge.property("screen") == "day"
    assert day.property("iso") == target_date


def test_day_from_the_rail_after_browsing_another_month_opens_on_today(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Leaving Month through its anchor loaded that month's week after Day asked for today's, and won."""
    bridge = root_bridge(show_material(qapp, window))
    session = window.session
    current = session.week_start
    today_iso = CLOCK.today().isoformat()
    bridge.showPage("month")
    settled(qapp, window)
    month = bridge.property("month")
    month.nextMonth()
    settled(qapp, window)
    pump(qapp)
    assert session.selected_month != today_iso[:7]
    bridge.showPage("day")
    settled(qapp, window)
    pump(qapp)
    assert session.planner_view == "day"
    assert bridge.property("day").property("iso") == today_iso
    assert session.week_start == current


def test_day_clicked_while_a_month_week_is_still_loading_opens_on_today(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Month, next month, Week, then Day before Week's load lands: that load must not move Day off today."""
    bridge = root_bridge(show_material(qapp, window))
    session = window.session
    current = session.week_start
    today_iso = CLOCK.today().isoformat()
    bridge.showPage("month")
    settled(qapp, window)
    bridge.property("month").nextMonth()
    settled(qapp, window)
    pump(qapp)
    # The other month's week stays on its way until Day has asked for today.
    session.client.hold()
    try:
        bridge.showPage("week")
        assert session.busy, "Week must still be loading the other month's week, or this tests nothing"
        bridge.showPage("day")
    finally:
        session.client.release()
    settled(qapp, window)
    wait_until(qapp, lambda: session.week_start == current, what="today's week loaded again")
    settled(qapp, window)
    pump(qapp)
    assert bridge.property("screen") == "day"
    assert bridge.property("day").property("iso") == today_iso
    assert session.week_start == current
