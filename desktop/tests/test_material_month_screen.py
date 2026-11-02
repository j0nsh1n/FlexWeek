"""The Material month on screen: the grid, chips, dots, the date bar, month moves and Open Day.

The window, its account and its clock come from the Material window tests. The clock is Thursday 19:00
of the current week, School runs weekday mornings, and a History essay has a session on that Thursday.
New accounts use the 12-hour clock. Sunday's due stamp from `sunday_due` is 23:59.
"""

from __future__ import annotations

import calendar
import os
from datetime import date, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.calendar import sunday_due  # noqa: E402
from desktop.native.hours.month import LOAD_WORDS  # noqa: E402
from desktop.native.window import WINDOW_MIN_WIDTH, NativeWindow  # noqa: E402
from desktop.tests.test_layouts_window import wait_until  # noqa: E402
from desktop.tests.test_material_window import (  # noqa: E402
    _named,
    _pump,
    _qml,
    _show_material,
)
from desktop.tests.test_material_window import qapp as _material_qapp  # noqa: E402
from desktop.tests.test_material_window import window as _material_window  # noqa: E402

qapp = _material_qapp
window = _material_window


def _grid(first_of_month: date, sunday_first: bool = False) -> list[str]:
    """The dates a month shows: whole weeks from the week start to the week end around it."""
    days = calendar.monthrange(first_of_month.year, first_of_month.month)[1]
    last = first_of_month.replace(day=days)
    lead = (first_of_month.weekday() + (1 if sunday_first else 0)) % 7
    tail = (6 - (last.weekday() + (1 if sunday_first else 0)) % 7) % 7
    start = first_of_month - timedelta(days=lead)
    return [(start + timedelta(days=n)).isoformat() for n in range((last - start).days + tail + 1)]


def _heading(iso: str) -> str:
    day = date.fromisoformat(iso)
    return f"{day.strftime('%A')} {day.day} {day.strftime('%B')}"


def _open_month(qapp: QApplication, window: NativeWindow) -> tuple[QObject, QObject]:
    root = _show_material(qapp, window)
    bridge = window._material_page.bridge
    bridge.showPage("month")
    month = bridge.property("month")
    here = window.session.today_iso()[:7]
    if window.session.selected_month != here:
        window.session.open_month(here)
    wait_until(qapp, lambda: (window.session.month_data or {}).get("month") == here)
    wait_until(qapp, lambda: len(_cells(root)) > 0)
    _pump(qapp)
    return root, month


def _cells(root: QObject) -> list[QObject]:
    return [item for item in _every(root) if str(item.objectName()).startswith("monthDate-")]


def _every(item: QObject) -> list[QObject]:
    found: list[QObject] = []
    for child in item.childItems() if hasattr(item, "childItems") else []:
        found.append(child)
        found.extend(_every(child))
    return found


def _on_screen(item: QObject) -> bool:
    current = item
    while current is not None:
        visible = current.property("visible") if hasattr(current, "property") else None
        if visible is False:
            return False
        current = current.parentItem() if hasattr(current, "parentItem") else None
    return True


def _cell(root: QObject, iso: str) -> QObject:
    found = [item for item in _cells(root) if str(item.objectName()) == f"monthDate-{iso}"]
    assert found, iso
    return found[0]


def _texts(item: QObject, name: str) -> list[str]:
    return [
        str(child.property("text"))
        for child in _every(item)
        if str(child.objectName()) == name and _on_screen(child)
    ]


def _named_on(item: QObject, name: str) -> list[QObject]:
    return [child for child in _every(item) if str(child.objectName()) == name and _on_screen(child)]


def _click(quick: QObject, item: QObject, dx: float = 8, dy: float = 8) -> None:
    """A real press and release at a point inside the item, in the Quick widget's own coordinates."""
    point = item.mapToScene(QPointF(dx, dy))
    QTest.mouseClick(
        quick,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(int(point.x()), int(point.y())),
    )
    _pump(QApplication.instance(), 10)


def test_the_month_screen_draws_the_dates_the_session_asked_for(
    qapp: QApplication, window: NativeWindow
) -> None:
    root, _month = _open_month(qapp, window)
    try:
        today = date.fromisoformat(window.session.today_iso())
        expected = _grid(today.replace(day=1))
        shown = [str(item.objectName())[len("monthDate-") :] for item in _cells(root)]
        assert shown == expected
        assert _texts(_qml(root, "materialMonth"), "monthWeekday") == [
            "Mon",
            "Tue",
            "Wed",
            "Thu",
            "Fri",
            "Sat",
            "Sun",
        ]
        marked = [
            str(item.parent().objectName())
            for item in _every(root)
            if str(item.objectName()) == "monthToday" and _on_screen(item)
        ]
        assert marked == [f"monthDate-{today.isoformat()}"]
        for item in _cells(root):
            iso = str(item.objectName())[len("monthDate-") :]
            assert item.property("inMonth") is (iso[:7] == today.isoformat()[:7]), iso
            assert float(item.property("opacity")) == (1.0 if iso[:7] == today.isoformat()[:7] else 0.45), iso
        assert _texts(_qml(root, "materialMonth"), "monthStudyCaption") == [LOAD_WORDS]
    finally:
        window._use_widgets_styles()


def test_a_date_shows_its_chips_in_the_account_clock(qapp: QApplication, window: NativeWindow) -> None:
    root, _month = _open_month(qapp, window)
    try:
        today = window.session.today_iso()
        due = sunday_due(window.session.week_start)
        sunday = due[:10]
        assert due.endswith("T23:59"), due
        chips = _texts(_cell(root, today), "monthChipText")
        assert chips == ["8:00 AM School", "6:45 PM History essay"]
        # 23:59 is the old end-of-day stamp, so Widgets month writes "Due" with no clock.
        assert _texts(_cell(root, sunday), "monthChipText") == ["Due History essay"]
        assert _named_on(_cell(root, today), "monthDot") == []
    finally:
        window._use_widgets_styles()


def test_an_overdue_deadline_uses_the_overdue_chip(qapp: QApplication, window: NativeWindow) -> None:
    root, _month = _open_month(qapp, window)
    gone = (date.fromisoformat(window.session.today_iso()) - timedelta(days=1)).isoformat()
    try:
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
        window.session.open_month(window.session.today_iso()[:7])
        wait_until(qapp, lambda: "Overdue Reading" in _texts(_cell(root, gone), "monthChipText"))
        assert "Overdue Reading" in _texts(_cell(root, gone), "monthChipText")
    finally:
        window._use_widgets_styles()


def test_picking_a_date_opens_a_bar_that_closes_and_opens_the_day(
    qapp: QApplication, window: NativeWindow
) -> None:
    root, month = _open_month(qapp, window)
    quick = window._material_page._quick
    try:
        today = window.session.today_iso()
        bar = _qml(root, "monthDateBar")
        assert bar.property("visible") is False
        _click(quick, _cell(root, today))
        assert bar.property("visible") is True
        assert _texts(bar, "monthDateHeading") == [_heading(today)]
        assert _texts(bar, "monthDateItem")[:2] == [
            "8:00 AM School · 6 h 30 min",
            "6:45 PM History essay · 1 h",
        ]
        _click(quick, _named(bar, "monthClose")[0], 20, 10)
        wait_until(qapp, lambda: bar.property("visible") is False)
        _click(quick, _cell(root, today))
        wait_until(qapp, lambda: bar.property("visible") is True)
        _click(quick, _named(bar, "monthOpenDay")[0], 20, 10)
        wait_until(qapp, lambda: window._material_page.bridge.property("screen") == "day")
        assert window.session.planner_view == "day"
        assert window.session.selected_day == today
        assert _qml(root, "materialDay").property("visible") is True
    finally:
        window._use_widgets_styles()


def test_previous_and_next_move_the_month(qapp: QApplication, window: NativeWindow) -> None:
    root, _month = _open_month(qapp, window)
    quick = window._material_page._quick
    try:
        today = date.fromisoformat(window.session.today_iso())
        shown = today.replace(day=1)
        following = date(shown.year + (shown.month == 12), shown.month % 12 + 1, 1)
        _click(quick, _qml(root, "monthNext"), 20, 20)
        wait_until(qapp, lambda: window.session.selected_month == following.isoformat()[:7])
        wait_until(
            qapp, lambda: f"monthDate-{following.isoformat()}" in [str(i.objectName()) for i in _cells(root)]
        )
        assert _named_on(_qml(root, "materialMonth"), "monthToday") == []
        _click(quick, _qml(root, "monthPrev"), 20, 20)
        _click(quick, _qml(root, "monthPrev"), 20, 20)
        previous = (shown - timedelta(days=1)).replace(day=1)
        wait_until(qapp, lambda: window.session.selected_month == previous.isoformat()[:7])
        wait_until(
            qapp, lambda: f"monthDate-{previous.isoformat()}" in [str(i.objectName()) for i in _cells(root)]
        )
    finally:
        window._use_widgets_styles()


def test_a_narrow_month_shows_dots_instead_of_chips(qapp: QApplication, window: NativeWindow) -> None:
    root, _month = _open_month(qapp, window)
    window.setMinimumWidth(360)
    window.resize(700, 800)
    _pump(qapp)
    try:
        today = window.session.today_iso()
        wait_until(qapp, lambda: float(_qml(root, "materialMonth").property("width")) < 768)
        wait_until(qapp, lambda: len(_named_on(_cell(root, today), "monthDot")) == 2)
        assert _texts(_cell(root, today), "monthChipText") == []
    finally:
        window.setMinimumWidth(WINDOW_MIN_WIDTH)
        window.resize(1280, 800)
        _pump(qapp)
        window._use_widgets_styles()


def test_the_study_time_switch_shows_the_load_bar(qapp: QApplication, window: NativeWindow) -> None:
    root, month = _open_month(qapp, window)
    quick = window._material_page._quick
    try:
        today = window.session.today_iso()
        assert month.property("showStudyTime") is False
        assert _named_on(_cell(root, today), "monthStudyBar") == []
        _click(quick, _qml(root, "monthStudyTime"), 26, 16)
        wait_until(qapp, lambda: month.property("showStudyTime") is True)
        wait_until(qapp, lambda: _named_on(_cell(root, today), "monthStudyBar") != [])
        assert _cell(root, today).property("plannedShare") == pytest.approx(60 / 180)
    finally:
        month.setShowStudyTime(False)
        window._use_widgets_styles()
