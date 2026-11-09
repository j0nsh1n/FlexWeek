# ruff: noqa: F811
"""Material 3 Settings > Advanced preview: the Week, Day and Month stages are real views on the draft, and
nothing done inside them (click, Tab, Return, Space, accessible Press) changes the student's live week.
"""

from __future__ import annotations

import copy
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, Qt, qInstallMessageHandler  # noqa: E402
from PySide6.QtGui import QAccessible  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_material_window import material_window, qapp  # noqa: E402, F401
from desktop.tests.material_support import named, pump  # noqa: E402
from desktop.tests.sheets.support_material_settings import (  # noqa: E402
    click,
    click_segment,
    open_settings,
    panel,
)
from desktop.tests.waiting import wait_until  # noqa: E402


def _everything_under(item: QObject) -> list[QObject]:
    found: list[QObject] = []
    for child in item.childItems() if hasattr(item, "childItems") else []:
        found.append(child)
        found.extend(_everything_under(child))
    return found


def test_the_advanced_preview_shows_a_month_and_a_day_without_touching_the_live_week(
    qapp: QApplication, material_window: NativeWindow
) -> None:
    window = material_window
    root = open_settings(qapp, window)
    settings = panel(window)
    settings.openAdvanced()
    pump(qapp, 10)

    # A fresh live session is on the week with no month history.
    assert window.session.planner_view == "week"
    assert window.session.selected_month is None
    assert window.session.month_data is None

    click_segment(qapp, window, named(root, "previewView")[0], "Month")
    wait_until(qapp, lambda: bool(named(root, "settingsPreviewMonth")))
    pump(qapp, 10)

    # Previewing the month left the live planner state untouched.
    assert window.session.planner_view == "week"
    assert window.session.selected_month is None
    assert window.session.month_data is None

    preview_month = named(root, "settingsPreviewMonth")[0]
    month_view = named(preview_month, "materialMonth")[0]
    month_bridge = month_view.property("month")
    assert month_bridge is not None, "MonthView in preview stage has null month bridge"
    dates = month_bridge.property("dates")
    assert dates is not None, "Month bridge in preview stage has null dates"
    assert dates.rowCount() >= 28, f"Expected dates.rowCount() >= 28, got {dates.rowCount()}"

    def month_cells() -> list[QObject]:
        return [i for i in _everything_under(month_view) if str(i.objectName()).startswith("monthDate-")]

    wait_until(qapp, lambda: len(month_cells()) >= 28, timeout=5.0)
    cells = month_cells()
    assert len(cells) >= 28, f"Expected >= 28 month cells, got {len(cells)}"
    shown = [c for c in cells if c.isVisible() and c.width() > 0 and c.height() > 0]
    assert len(shown) >= 28, f"Expected >= 28 visible cells with geometry, got {len(shown)}"
    day_numbers = named(month_view, "monthDayNumber")
    assert len(day_numbers) >= 28, f"Expected >= 28 day numbers, got {len(day_numbers)}"
    day_texts = [str(t.property("text")).strip() for t in day_numbers if str(t.property("text")).strip()]
    assert len(day_texts) >= 28, f"Expected non-empty day number texts, got {len(day_texts)}"
    weekdays = named(month_view, "monthWeekday")
    assert len(weekdays) == 7, f"Expected 7 weekday headers, got {len(weekdays)}"

    click_segment(qapp, window, named(root, "previewView")[0], "Day")
    wait_until(qapp, lambda: bool(named(root, "settingsPreviewDay")))
    pump(qapp, 10)

    preview_day = named(root, "settingsPreviewDay")[0]
    day_view = named(preview_day, "materialDay")[0]
    assert day_view.property("board") is not None, "DayView in preview stage has null board (day bridge)"
    previous, following = named(day_view, "dayPrevious"), named(day_view, "dayNext")
    assert len(previous) > 0 and previous[0].isVisible(), "Day previous button missing"
    assert len(following) > 0 and following[0].isVisible(), "Day next button missing"
    month_side = named(day_view, "dayMonthSide")
    assert len(month_side) > 0 and month_side[0].isVisible(), "dayMonthSide missing or hidden"
    assert month_side[0].width() > 0, f"dayMonthSide width is 0: {month_side[0].width()}"
    assert len(named(day_view, "dayLeftLine")) > 0, "dayLeftLine text item missing"


def test_preview_keyboard_and_action_isolation(qapp: QApplication, material_window: NativeWindow) -> None:
    """Advanced preview controls cannot change the live planner state.

    A click on dayNext in the preview, Return and Space on it (even with focus forced there), and its
    accessible action leave the live day, view, preferences, blocks and homework as they were. No Tab stop
    in the passive preview reaches its day arrows: a full Tab cycle visits only the Week/Day/Month and
    Fit/Actual switches. The Settings controls around it still update the preview.
    """
    window = material_window
    root = open_settings(qapp, window)
    settings = panel(window)
    settings.openAdvanced()
    pump(qapp, 10)
    click_segment(qapp, window, named(root, "previewView")[0], "Day")
    wait_until(qapp, lambda: bool(named(root, "settingsPreviewDay")))
    pump(qapp, 10)
    preview_day = named(root, "settingsPreviewDay")[0]
    day_view = named(preview_day, "materialDay")[0]
    day_next = named(day_view, "dayNext")[0]
    day_prev = named(day_view, "dayPrevious")[0]
    session = window.session
    initial_day = session.selected_day
    initial_view = session.planner_view
    initial_prefs = copy.deepcopy(session.preferences or {})
    initial_blocks = copy.deepcopy(session.blocks or [])
    initial_assignments = copy.deepcopy(session.assignments or {})

    click(qapp, window, day_next)
    assert (session.selected_day, session.planner_view) == (initial_day, initial_view), (
        "Pointer click on preview dayNext mutated live planner state"
    )

    quick = window._material_page._quick
    trail: list[str] = []
    for _ in range(120):
        QTest.keyClick(quick, Qt.Key.Key_Tab)
        qapp.processEvents()
        focused = quick.quickWindow().activeFocusItem()
        trail.append(focused.objectName() if focused else "<none>")
        assert focused is not day_next and focused is not day_prev, (
            f"Tab reached a preview day arrow, which must not be a Tab stop. Focus trail: {trail}"
        )
    assert "previewView" in trail and "previewFit" in trail, f"Preview switches not in Tab order: {trail}"

    for arrow in (day_next, day_prev):
        arrow.forceActiveFocus()
        qapp.processEvents()
        for key in (Qt.Key.Key_Return, Qt.Key.Key_Space):
            QTest.keyClick(quick, key)
            pump(qapp, 5)
            assert (session.selected_day, session.planner_view) == (initial_day, initial_view), (
                f"{key} on preview {arrow.objectName()} mutated live planner state"
            )

    accessible = day_next.property("Accessible")
    if accessible is not None and hasattr(accessible, "pressAction"):
        accessible.pressAction()
        pump(qapp, 5)
        assert (session.selected_day, session.planner_view) == (initial_day, initial_view)

    assert session.selected_day == initial_day
    assert session.planner_view == initial_view
    assert (session.preferences or {}) == initial_prefs
    assert (session.blocks or []) == initial_blocks
    assert (session.assignments or {}) == initial_assignments

    click_segment(qapp, window, named(root, "previewView")[0], "Week")
    wait_until(qapp, lambda: bool(named(root, "settingsPreviewWeek")))
    pump(qapp, 5)
    assert named(root, "settingsPreviewWeek")[0].isVisible()


def test_week_preview_completion_is_inert_and_has_no_qml_error(
    qapp: QApplication, material_window: NativeWindow
) -> None:
    window = material_window
    root = open_settings(qapp, window)
    settings = panel(window)
    messages: list[str] = []
    session = window.session

    def state():
        return copy.deepcopy(
            (
                session.selected_day,
                session.planner_view,
                session.preferences,
                session.blocks,
                session.assignments,
            )
        )

    settings.openAdvanced()
    settings.setPreviewView("week")
    pump(qapp)
    preview = named(root, "settingsPreviewWeek")[0]
    blocks = [item for item in named(preview, "weekBlock") if item.property("homework")]
    assert blocks, "The preview must contain an actual homework block"
    item = blocks[0]
    before = state()
    previous_handler = qInstallMessageHandler(lambda _kind, _context, text: messages.append(text))
    try:
        item.forceActiveFocus()
        QTest.keyClick(window._material_page._quick, Qt.Key.Key_Return)
        pump(qapp)
        interface = QAccessible.queryAccessibleInterface(item)
        assert interface is not None
        action = interface.actionInterface()
        assert action is not None and "Press" in action.actionNames()
        action.doAction("Press")
        pump(qapp)
        finishes = named(item, "weekBlockFinish")
        if finishes:
            finishes[0].forceActiveFocus()
            QTest.keyClick(window._material_page._quick, Qt.Key.Key_Return)
            pump(qapp)
    finally:
        qInstallMessageHandler(previous_handler)
    assert not any("TypeError" in text for text in messages), messages
    assert state() == before
