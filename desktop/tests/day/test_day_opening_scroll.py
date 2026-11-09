# ruff: noqa: F811
"""Where the Material Day hour column opens scrolled: the evening near the top on today, the first
block of the day on another day, and not before the week it needs has loaded.

The expected scroll is the opening rule: the opening minute sits 45 minutes below the top of the
pane, or less in a pane too short for that. It is worked out here from the rule, not read from the
scroller.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.hours.zoom import NOW_MARGIN  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_material_day import (  # noqa: E402
    bridge_of,
    day_item,
    open_day_page,
    seed_thursday,
)
from desktop.tests.light_app import open_light  # noqa: E402, F401
from desktop.tests.material_support import pump, qml  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.window_support import qapp, settled  # noqa: E402, F401

NOW_MINUTE = 19 * 60


@pytest.fixture()
def window(qapp: QApplication, open_light) -> NativeWindow:
    return seed_thursday(qapp, open_light((1280, 800)), hour=19, soccer=True)


def _opening_above(view: float, row: int) -> float:
    """45 minutes above now, unless the pane is shorter than that margin plus one hour."""
    margin = NOW_MARGIN / 60 * row
    if view < margin + row:
        return min(margin, max(8.0, view * 0.08))
    return margin


def test_it_opens_scrolled_so_nineteen_is_near_the_top(qapp: QApplication, window: NativeWindow) -> None:
    root = open_day_page(qapp, window)
    scroller = qml(day_item(root), "dayScroller")
    row = int(bridge_of(window).property("dayHourRow"))
    now_y = 19 * row
    essay_y = 18.75 * row
    content_y = float(scroller.property("contentY"))
    view_h = float(scroller.property("height"))
    assert view_h > 40
    above = _opening_above(view_h, row)
    assert content_y <= now_y <= content_y + view_h
    assert content_y <= essay_y <= content_y + view_h
    assert abs((now_y - content_y) - above) < 2
    assert int(bridge_of(window).property("day").property("openingMinute")) == NOW_MINUTE

    quick = window._material_page._quick
    quick.setFocus()
    pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_Equal, Qt.KeyboardModifier.ControlModifier)
    pump(qapp)
    day_bridge = bridge_of(window).property("day")
    day_bridge.previousDay()
    settled(qapp, window)
    pump(qapp)
    day_bridge.nextDay()
    settled(qapp, window)
    pump(qapp)
    row = int(bridge_of(window).property("dayHourRow"))
    assert row == 72
    scroller = qml(day_item(root), "dayScroller")
    now_y = 19 * row
    essay_y = 18.75 * row
    content_y = float(scroller.property("contentY"))
    view_h = float(scroller.property("height"))
    above = _opening_above(view_h, row)
    assert content_y <= now_y <= content_y + view_h
    assert content_y <= essay_y <= content_y + view_h
    assert abs((now_y - content_y) - above) < 2


def test_opening_a_date_in_the_next_week_waits_for_that_week(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Next past Sunday loads the next week; Day opens at that Monday's first block once it lands,
    not at the fallback hour it had while the week was loading."""
    session = window.session
    following = (date.fromisoformat(window.home_week) + timedelta(days=7)).isoformat()
    session.load_week(following)
    settled(qapp, window)
    session.add_block(
        {
            "id": "mon-art",
            "title": "Art club",
            "kind": "locked",
            "category": "extra",
            "start": "14:00",
            "duration_min": 60,
            "days": [0],
        }
    )
    session.save()
    settled(qapp, window)
    session.load_week(window.home_week)
    settled(qapp, window)
    root = open_day_page(qapp, window)
    day_bridge = bridge_of(window).property("day")
    for _ in range(4):
        day_bridge.nextDay()
        settled(qapp, window)
        pump(qapp)
    wait_until(qapp, lambda: session.week_start == following, what="the next week loaded")
    settled(qapp, window)
    pump(qapp)
    assert int(day_bridge.property("dayIndex")) == 0
    assert int(day_bridge.property("openingMinute")) == 14 * 60
    scroller = qml(day_item(root), "dayScroller")
    row = int(bridge_of(window).property("dayHourRow"))
    view_h = float(scroller.property("height"))
    wait_until(
        qapp,
        lambda: abs(14 * row - float(scroller.property("contentY")) - _opening_above(view_h, row)) < 2,
        what="Day scrolled to the Monday's first block",
    )


def test_a_block_in_progress_opens_with_its_top_in_view(qapp: QApplication, open_light) -> None:
    """The History essay (18:45-19:45) is on at 19:40: now is 55 minutes past its start, so opening
    45 minutes above now would cut its top and its done circle. It opens with the block's top, and the
    hour label for its start, in view instead, with now still on screen."""
    window = seed_thursday(qapp, open_light((1280, 800)), hour=19, minute=40)
    root = open_day_page(qapp, window)
    scroller = qml(day_item(root), "dayScroller")
    row = int(bridge_of(window).property("dayHourRow"))
    content_y = float(scroller.property("contentY"))
    view_h = float(scroller.property("height"))
    essay_y = 18.75 * row
    now_y = (19 * 60 + 40) / 60 * row
    above = _opening_above(view_h, row)
    assert content_y <= essay_y - above + 2
    assert content_y <= 18 * row
    assert content_y <= now_y <= content_y + view_h


def test_a_long_block_in_progress_does_not_pull_now_off_the_top(qapp: QApplication, open_light) -> None:
    """School (08:00-14:30) is on at 14:00: its top is far above, so Day still opens 45 minutes above now."""
    window = seed_thursday(qapp, open_light((1280, 800)), hour=14)
    root = open_day_page(qapp, window)
    scroller = qml(day_item(root), "dayScroller")
    row = int(bridge_of(window).property("dayHourRow"))
    content_y = float(scroller.property("contentY"))
    view_h = float(scroller.property("height"))
    assert abs((14 * row - content_y) - _opening_above(view_h, row)) < 2


def test_a_block_starting_on_the_hour_keeps_its_start_label_clear_of_the_zoom_buttons(
    qapp: QApplication, open_light
) -> None:
    """Soccer (16:00-17:30) is on at 16:11: opening 45 minutes above now puts the 4:00 PM line 34 px under
    the top, where its label hides behind the zoom buttons. It opens 45 minutes above the block instead."""
    window = seed_thursday(qapp, open_light((1280, 800)), hour=16, minute=11, soccer=True)
    root = open_day_page(qapp, window)
    scroller = qml(day_item(root), "dayScroller")
    row = int(bridge_of(window).property("dayHourRow"))
    content_y = float(scroller.property("contentY"))
    view_h = float(scroller.property("height"))
    assert abs((16 * row - content_y) - _opening_above(view_h, row)) < 2
    now_y = (16 * 60 + 11) / 60 * row
    assert content_y <= now_y <= content_y + view_h
