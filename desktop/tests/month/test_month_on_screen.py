# ruff: noqa: F811
"""The Material month on screen: the grid, chips, dots, the date bar, month moves and Open Day.

The clock is Thursday 19:00 of the account's first week, School runs weekday mornings, and a History
essay has a session on that Thursday (support_material_month.seed_school_and_essay). New accounts use
the 12-hour clock. Sunday's due stamp from `sunday_due` is 23:59.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from datetime import date, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.calendar import sunday_due  # noqa: E402
from desktop.native.hours.month import LOAD_WORDS  # noqa: E402
from desktop.native.window import WINDOW_MIN_WIDTH, NativeWindow  # noqa: E402
from desktop.tests.light_app import open_light  # noqa: E402, F401
from desktop.tests.material_support import pump, qml  # noqa: E402
from desktop.tests.month.support_material_month import (  # noqa: E402
    cell,
    cells,
    click,
    grid,
    heading,
    named_on,
    open_month,
    seed_school_and_essay,
    shown_dates,
    texts,
)
from desktop.tests.waiting import wait_until  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-material-month-screen"])


@pytest.fixture()
def window(qapp: QApplication, open_light: Callable[..., NativeWindow]) -> NativeWindow:
    made = open_light((1280, 800))
    seed_school_and_essay(made)
    return made


def test_the_month_screen_draws_the_dates_the_session_asked_for(
    qapp: QApplication, window: NativeWindow
) -> None:
    root, _month = open_month(qapp, window)
    today = date.fromisoformat(window.session.today_iso())
    assert shown_dates(root) == grid(today.replace(day=1))
    assert texts(qml(root, "materialMonth"), "monthWeekday") == [
        "Mon",
        "Tue",
        "Wed",
        "Thu",
        "Fri",
        "Sat",
        "Sun",
    ]
    marked = [str(item.parent().objectName()) for item in named_on(root, "monthToday")]
    assert marked == [f"monthDate-{today.isoformat()}"]
    for item in cells(root):
        iso = str(item.objectName())[len("monthDate-") :]
        assert item.property("inMonth") is (iso[:7] == today.isoformat()[:7]), iso
    assert texts(qml(root, "materialMonth"), "monthStudyCaption") == [LOAD_WORDS]


def test_a_date_shows_its_chips_in_the_account_clock(qapp: QApplication, window: NativeWindow) -> None:
    root, _month = open_month(qapp, window)
    today = window.session.today_iso()
    due = sunday_due(window.session.week_start)
    sunday = due[:10]
    assert due.endswith("T23:59"), due
    assert texts(cell(root, today), "monthChipText") == ["8:00 AM School", "6:45 PM History essay"]
    # 23:59 is the end-of-day stamp, so the chip says "Due" with no clock. Sunday 8 November is in
    # the November grid (it runs from Monday 26 October to Sunday 6 December).
    assert sunday in shown_dates(root)
    assert texts(cell(root, sunday), "monthChipText") == ["Due History essay"]
    assert named_on(cell(root, today), "monthDot") == []


def test_an_overdue_deadline_uses_the_overdue_chip(qapp: QApplication, window: NativeWindow) -> None:
    root, _month = open_month(qapp, window)
    today = date.fromisoformat(window.session.today_iso())
    gone = [iso for iso in grid(today.replace(day=1)) if iso < today.isoformat()][-1]
    window.session.add_homework(
        {
            "id": "reading",
            "title": "Reading",
            "due": f"{gone}T09:00",
            "estimate_min": 15,
            "revision": 0,
        }
    )
    window.session.save()
    wait_until(qapp, lambda: not window.session.busy and not window.session.dirty)
    window.session.open_month(window.session.today_iso()[:7])
    wait_until(qapp, lambda: not window.session.busy)
    wait_until(
        qapp,
        lambda: "Overdue Reading" in texts(cell(root, gone), "monthChipText"),
        what=lambda: f"the chips were {texts(cell(root, gone), 'monthChipText')}",
    )


def test_picking_a_date_opens_a_bar_that_closes_and_opens_the_day(
    qapp: QApplication, window: NativeWindow
) -> None:
    root, month = open_month(qapp, window)
    quick = window._material_page._quick
    today = window.session.today_iso()
    bar = qml(root, "monthDateBar")
    month.closeDate()
    pump(qapp)
    assert bar.property("visible") is False
    target = cell(root, today)
    click(quick, target, float(target.property("width")) / 2, float(target.property("height")) / 2)
    wait_until(qapp, lambda: bar.property("visible") is True)
    assert texts(bar, "monthDateHeading") == [heading(today)]
    assert texts(bar, "monthDateItem")[:2] == [
        "8:00 AM School · 6 h 30 min",
        "6:45 PM History essay · 1 h",
    ]
    closer = qml(root, "monthClose")
    assert closer.property("visible") is True
    closer.clicked.emit()
    wait_until(qapp, lambda: month.property("barOpen") is False)
    wait_until(qapp, lambda: bar.property("visible") is False)
    target = cell(root, today)
    click(quick, target, float(target.property("width")) / 2, float(target.property("height")) / 2)
    wait_until(qapp, lambda: bar.property("visible") is True)
    qml(root, "monthOpenDay").clicked.emit()
    wait_until(qapp, lambda: window._material_page.bridge.property("screen") == "day")
    assert window.session.planner_view == "day"
    assert window.session.selected_day == today
    assert qml(root, "materialDay").property("visible") is True


def test_previous_and_next_move_the_month(qapp: QApplication, window: NativeWindow) -> None:
    root, _month = open_month(qapp, window)
    quick = window._material_page._quick
    today = date.fromisoformat(window.session.today_iso())
    shown = today.replace(day=1)
    following = date(shown.year + (shown.month == 12), shown.month % 12 + 1, 1)
    click(quick, qml(root, "monthNext"), 20, 20)
    wait_until(qapp, lambda: window.session.selected_month == following.isoformat()[:7])
    wait_until(qapp, lambda: following.isoformat() in shown_dates(root))
    assert named_on(qml(root, "materialMonth"), "monthToday") == []
    click(quick, qml(root, "monthPrev"), 20, 20)
    click(quick, qml(root, "monthPrev"), 20, 20)
    previous = (shown - timedelta(days=1)).replace(day=1)
    wait_until(qapp, lambda: window.session.selected_month == previous.isoformat()[:7])
    wait_until(qapp, lambda: previous.isoformat() in shown_dates(root))


def test_the_minimum_desktop_width_still_shows_chips(qapp: QApplication, window: NativeWindow) -> None:
    """800px is the product floor; the rail is still up, so this is not a phone and chips stay."""
    root, _month = open_month(qapp, window)
    window.resize(WINDOW_MIN_WIDTH, 800)
    today = window.session.today_iso()
    wait_until(qapp, lambda: qml(root, "materialMonth").property("phone") is False)
    wait_until(
        qapp,
        lambda: texts(cell(root, today), "monthChipText") == ["8:00 AM School", "6:45 PM History essay"],
        what=lambda: f"the chips were {texts(cell(root, today), 'monthChipText')}",
    )
    assert named_on(cell(root, today), "monthDot") == []


def test_a_phone_month_shows_dots_instead_of_chips(qapp: QApplication, window: NativeWindow) -> None:
    root, _month = open_month(qapp, window)
    window.setMinimumWidth(360)
    window.resize(700, 800)
    today = window.session.today_iso()
    wait_until(qapp, lambda: qml(root, "materialMonth").property("phone") is True)
    wait_until(qapp, lambda: len(named_on(cell(root, today), "monthDot")) == 2)
    assert texts(cell(root, today), "monthChipText") == []


def test_a_short_date_keeps_one_chip_and_counts_the_rest(qapp: QApplication, window: NativeWindow) -> None:
    root, _month = open_month(qapp, window)
    window.resize(1280, 400)
    today = window.session.today_iso()
    wait_until(qapp, lambda: int(cell(root, today).property("rowsFit")) == 1)
    assert texts(cell(root, today), "monthChipText") == ["8:00 AM School"]
    assert texts(cell(root, today), "monthMore") == ["and 1 more"]


def test_the_study_time_switch_shows_the_study_fill(qapp: QApplication, window: NativeWindow) -> None:
    root, month = open_month(qapp, window)
    quick = window._material_page._quick
    today = window.session.today_iso()
    assert month.property("showStudyTime") is False
    assert named_on(cell(root, today), "monthStudyFill") == []
    click(quick, qml(root, "monthStudyTime"), 26, 16)
    wait_until(qapp, lambda: month.property("showStudyTime") is True)
    wait_until(qapp, lambda: named_on(cell(root, today), "monthStudyFill") != [])
    assert cell(root, today).property("plannedShare") == pytest.approx(60 / 180)
    month.setShowStudyTime(False)
    wait_until(qapp, lambda: qml(root, "monthStudyTime").property("checked") is False)
    wait_until(qapp, lambda: named_on(cell(root, today), "monthStudyFill") == [])
