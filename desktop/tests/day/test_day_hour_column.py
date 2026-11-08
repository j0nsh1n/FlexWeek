# ruff: noqa: F811
"""Material Day as one hour column: which blocks it shows, the now line, other days, weekends, and
how a block is reached by click, Tab, Enter and Space.

Expected values come from the account's own blocks (School, Soccer, and the History essay planned for
18:45) with the clock held on Thursday at 19:00, not from reading what the QML prints. Where the
blocks sit, their sizes and the now line's stacking are pictures (pictures/_day_g01.py).
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

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_material_day import (  # noqa: E402
    NOW_DAY,
    block_named,
    blocks_by_title,
    bridge_of,
    click,
    day_item,
    open_day_page,
    pref,
    scroll_block_into_view,
    seed_thursday,
)
from desktop.tests.light_app import open_light  # noqa: E402, F401
from desktop.tests.material_support import named, pump, qml, visuals  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.window_support import qapp, settled  # noqa: E402, F401

NOW_MINUTE = 19 * 60


@pytest.fixture()
def window(qapp: QApplication, open_light) -> NativeWindow:
    return seed_thursday(qapp, open_light((1280, 800)), hour=19, soccer=True)


def test_day_shows_the_three_blocks_and_hides_the_lists(qapp: QApplication, window: NativeWindow) -> None:
    root = open_day_page(qapp, window)
    day = day_item(root)
    bridge = bridge_of(window)
    assert int(bridge.property("day").property("dayIndex")) == NOW_DAY

    blocks = blocks_by_title(day)
    assert set(blocks) == {"School", "Soccer", "History essay"}
    assert blocks["School"].property("past") is True
    assert blocks["Soccer"].property("past") is True
    assert blocks["History essay"].property("past") is False
    assert blocks["History essay"].property("homework") is True

    names = {str(item.objectName()) for item in visuals(day)}
    assert "dayUpNext" not in names
    assert "dayDone" not in names
    assert "dayFinish" not in names
    assert "dayLeftLine" in names
    assert "dayPrevious" in names
    assert "dayNow" in names


def test_the_now_line_is_on_today_at_nineteen_and_absent_on_another_day(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = open_day_page(qapp, window)
    line = qml(day_item(root), "nowLine")
    assert line.property("visible") is True
    assert int(bridge_of(window).property("nowMinute")) == NOW_MINUTE

    bridge_of(window).property("day").nextDay()
    settled(qapp, window)
    pump(qapp)
    assert qml(day_item(root), "nowLine").property("visible") is False


def test_the_previous_day_shows_that_days_blocks_and_a_date_outside_the_week_is_empty(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = open_day_page(qapp, window)
    day_bridge = bridge_of(window).property("day")
    day_bridge.previousDay()
    settled(qapp, window)
    pump(qapp)
    assert int(day_bridge.property("dayIndex")) == NOW_DAY - 1
    assert set(blocks_by_title(day_item(root))) == {"School"}

    session = window.session
    outside = (date.fromisoformat(session.week_start) + timedelta(days=14)).isoformat()
    session.selected_day = outside
    day_bridge.reload(str(day_bridge._mode))
    window._material_page.publish()
    pump(qapp)
    assert int(day_bridge.property("dayIndex")) == -1
    assert named(day_item(root), "weekBlock") == []


def test_day_shows_saturday_when_week_hides_weekends(qapp: QApplication, window: NativeWindow) -> None:
    session = window.session
    session.add_block(
        {
            "id": "sat-club",
            "title": "Saturday club",
            "kind": "locked",
            "category": "extra",
            "start": "10:00",
            "duration_min": 60,
            "days": [5],
        }
    )
    session.save()
    settled(qapp, window)
    root = open_day_page(qapp, window, weekends=False)
    day_bridge = bridge_of(window).property("day")
    day_bridge.nextDay()
    settled(qapp, window)
    pump(qapp)
    day_bridge.nextDay()
    settled(qapp, window)
    pump(qapp)
    assert int(day_bridge.property("dayIndex")) == 5
    assert "Saturday club" in blocks_by_title(day_item(root))
    bridge_of(window).showPage("week")
    pump(qapp)
    assert int(bridge_of(window).property("week").property("columns")) == 5
    assert len(named(root, "dayHeader")) == 5
    week_blocks = named(qml(root, "materialWeek"), "weekBlock")
    week_titles = [str(block.property("title")) for block in week_blocks]
    assert "Saturday club" not in week_titles
    pref(window, show_weekends=True)


def test_a_focused_block_keeps_focus_across_an_unchanged_refresh(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = open_day_page(qapp, window)
    essay = block_named(day_item(root), "History essay")
    essay.forceActiveFocus()
    pump(qapp)
    assert essay.property("activeFocus") is True
    bridge_of(window).refresh()
    pump(qapp)
    essay = block_named(day_item(root), "History essay")
    assert essay.property("activeFocus") is True

    bridge_of(window).showPage("week")
    pump(qapp)
    week = qml(root, "materialWeek")
    essay = block_named(week, "History essay")
    essay.forceActiveFocus()
    pump(qapp)
    assert essay.property("activeFocus") is True
    bridge_of(window).refresh()
    pump(qapp)
    essay = block_named(qml(root, "materialWeek"), "History essay")
    assert essay.property("activeFocus") is True


def test_ticking_the_essay_and_opening_school_use_the_week_bridge_calls(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = open_day_page(qapp, window)
    day = day_item(root)
    session = window.session
    sheets = bridge_of(window).property("sheets")
    toggled: list[tuple[str, bool]] = []
    real_complete = session.complete_homework

    def spy_complete(assignment_id: str, completed: bool = True) -> None:
        toggled.append((assignment_id, completed))
        real_complete(assignment_id, completed)

    session.complete_homework = spy_complete
    try:
        essay = block_named(day, "History essay")
        finish = named(essay, "weekBlockFinish")[0]
        click(window, finish)
        wait_until(
            qapp,
            lambda: not session.busy and bool(session.assignments["essay"].get("completed")),
        )
        assert toggled == [("essay", True)]
        assert session.assignments["essay"].get("completed") is True

        school = block_named(day_item(root), "School")
        scroll_block_into_view(qapp, day_item(root), school)
        click(window, school)
        wait_until(qapp, lambda: sheets.kind == "block")
        draft = sheets._block
        assert draft is not None
        assert draft.original["id"] == "school"
        assert draft.occurrence_day == NOW_DAY
        sheets.forceClose()
        pump(qapp)
    finally:
        session.complete_homework = real_complete


def test_every_day_block_opens_from_a_click_tab_and_enter_and_space_toggles_homework(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = open_day_page(qapp, window)
    day = day_item(root)
    sheets = bridge_of(window).property("sheets")
    quick = window._material_page._quick
    blocks = blocks_by_title(day)
    school = blocks["School"]
    soccer = blocks["Soccer"]
    essay = blocks["History essay"]
    assert school.property("activeFocusOnTab") is True
    assert soccer.property("activeFocusOnTab") is True
    assert essay.property("activeFocusOnTab") is True

    scroll_block_into_view(qapp, day, soccer)
    click(window, soccer)
    wait_until(qapp, lambda: sheets.kind == "block")
    assert sheets._block is not None
    assert sheets._block.original["id"] == "soccer"
    sheets.forceClose()
    pump(qapp)

    school.forceActiveFocus()
    pump(qapp)
    assert school.property("activeFocus") is True
    QTest.keyClick(quick, Qt.Key.Key_Tab)
    pump(qapp)
    soccer = blocks_by_title(day_item(root))["Soccer"]
    assert soccer.property("activeFocus") is True
    QTest.keyClick(quick, Qt.Key.Key_Return)
    wait_until(qapp, lambda: sheets.kind == "block")
    assert sheets._block is not None
    assert sheets._block.original["id"] == "soccer"
    sheets.forceClose()
    pump(qapp)

    essay = blocks_by_title(day_item(root))["History essay"]
    essay.forceActiveFocus()
    pump(qapp)
    assert essay.property("activeFocus") is True
    assert window.session.assignments["essay"].get("completed") in (None, False)
    QTest.keyClick(quick, Qt.Key.Key_Space)
    wait_until(
        qapp,
        lambda: not window.session.busy and bool(window.session.assignments["essay"].get("completed")),
    )
    assert sheets.kind == ""
