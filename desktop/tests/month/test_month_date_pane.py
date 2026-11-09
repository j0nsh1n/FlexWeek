"""Month's date pane: the study-time switch and Open Day, the drawer under 1150 pixels, the arrow keys,
the study time a date's homework adds up to, and overdue homework living in Unfinished."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths, Qt  # noqa: E402
from PySide6.QtTest import QSignalSpy, QTest  # noqa: E402
from PySide6.QtWidgets import QAbstractButton, QApplication, QWidget  # noqa: E402

from desktop.native.hours.month import MonthGrid, month_cells  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import window  # noqa: E402, F401
from desktop.tests.month.support_month import september  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.window_support import settled  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-month-pane-test"])


def shown_grid(qapp: QApplication, width: int = 1280) -> MonthGrid:
    grid = MonthGrid()
    grid.resize(width, 700)
    grid.set_month(september(), False, "2026-09-10")
    grid.show()
    qapp.processEvents()
    return grid


def click_date(qapp: QApplication, grid: MonthGrid, iso: str) -> None:
    point = grid.canvas.mapFromGlobal(grid.canvas.cell_point(iso))
    QTest.mouseClick(grid.canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
    qapp.processEvents()


def test_the_date_pane_has_the_study_time_switch_and_open_day(qapp: QApplication) -> None:
    grid = shown_grid(qapp)
    assert grid.pane.load_switch.text() == "Show study time per date"
    assert grid.pane.open.text() == "Open Day"
    assert grid.pane.heading.text() == "Thursday 10 September"
    assert grid.overdue.isHidden()
    assert grid.overdue.text() == ""
    grid.pane.load_switch.setChecked(True)
    assert grid.canvas._show_load is True
    grid.close()


def test_the_date_pane_is_a_drawer_under_1150(qapp: QApplication) -> None:
    grid = shown_grid(qapp)
    assert grid.width() >= 1150
    assert grid._split.indexOf(grid.pane) >= 0
    grid.resize(1149, 700)
    qapp.processEvents()
    assert grid.width() < 1150
    assert grid._split.indexOf(grid.pane) < 0
    assert grid.pane.parent() is grid
    # A drawer starts closed, so Saturday and Sunday are not under it.
    assert grid.pane.isHidden()
    click_date(qapp, grid, "2026-09-12")
    assert grid.pane.isVisible()
    assert grid.pane.heading.text() == "Saturday 12 September"
    assert grid.pane.close_button.isVisible() and grid.pane.close_button.text() == "Close"
    QTest.keyClick(grid.pane, Qt.Key.Key_Escape)
    qapp.processEvents()
    assert grid.pane.isHidden()
    click_date(qapp, grid, "2026-09-13")
    grid.pane.close_button.click()
    qapp.processEvents()
    assert grid.pane.isHidden()
    # Wide again, the pane is beside the grid and has nothing to close.
    grid.resize(1280, 700)
    qapp.processEvents()
    assert grid._split.indexOf(grid.pane) >= 0
    assert grid.pane.isVisible() and grid.pane.close_button.isHidden()
    grid.close()


def test_arrow_keys_move_the_date_and_enter_opens_it(qapp: QApplication) -> None:
    grid = shown_grid(qapp)
    opened = QSignalSpy(grid.day_activated)
    grid.canvas.setFocus()
    QTest.keyClick(grid.canvas, Qt.Key.Key_Right)
    assert grid.canvas.selected == "2026-09-11"
    assert grid.pane.heading.text() == "Friday 11 September"
    QTest.keyClick(grid.canvas, Qt.Key.Key_Down)
    assert grid.canvas.selected == "2026-09-18"
    QTest.keyClick(grid.canvas, Qt.Key.Key_Up)
    QTest.keyClick(grid.canvas, Qt.Key.Key_Left)
    assert grid.canvas.selected == "2026-09-10"
    assert opened.count() == 0
    QTest.keyClick(grid.canvas, Qt.Key.Key_Return)
    assert opened.count() == 1 and opened.at(0) == ["2026-09-10"]
    # Narrow, Enter opens the drawer first and sends the keyboard to Open Day.
    grid.resize(1024, 700)
    qapp.processEvents()
    grid.canvas.setFocus()
    QTest.keyClick(grid.canvas, Qt.Key.Key_Right)
    assert grid.pane.isHidden()
    QTest.keyClick(grid.canvas, Qt.Key.Key_Return)
    qapp.processEvents()
    assert grid.pane.isVisible() and grid.pane.heading.text() == "Friday 11 September"
    assert opened.count() == 1
    grid.close()


def test_another_weeks_homework_counts_as_study_time_and_ticks_only_when_done(qapp: QApplication) -> None:
    snapshot = september()
    for day in snapshot["days"]:
        if day["date"] == "2026-09-22":
            day["blocks"] = [
                {"id": "a", "title": "Essay", "start": "16:00", "duration_min": 45, "category": None,
                 "assignment_id": "essay", "completed": True},
                {"id": "b", "title": "Lab", "start": "18:00", "duration_min": 30, "category": None,
                 "assignment_id": "lab", "completed": False},
                {"id": "c", "title": "Soccer", "start": "19:00", "duration_min": 60, "category": "sports",
                 "assignment_id": None, "completed": False},
            ]
    cell = next(cell for cell in month_cells(snapshot, {}, "2026-09-10") if cell.iso == "2026-09-22")
    # 45 + 30 min of homework sessions planned, the 45 finished; Soccer is not homework.
    assert (cell.planned_min, cell.completed_min) == (75, 45)
    grid = MonthGrid()
    grid.set_month(snapshot, False, "2026-09-10")
    grid.select("2026-09-22")
    lines = [grid.pane.rows.itemAt(i).widget().text() for i in range(grid.pane.rows.count())]
    assert lines[0].startswith("✓ ") and lines[0].endswith("Essay · 45 min")
    assert not lines[1].startswith("✓ ") and lines[1].endswith("Lab · 30 min")
    assert grid.pane.summary.text() == "1 h 15 min homework planned · 45 min completed"
    grid.close()


def test_month_keeps_overdue_in_unfinished_not_a_strip(qapp: QApplication, window: NativeWindow) -> None:  # noqa: F811
    window.resize(1280, 800)
    window.findChild(QAbstractButton, "viewMonth").click()
    wait_until(qapp, lambda: window.session.planner_view == "month")
    settled(qapp, window)
    assert window.findChild(QWidget, "weekStatusStrip") is None
    assert window.month_grid.overdue.isHidden()
    assert window.month_grid.overdue.text() == ""
    window._sync_more_menu()
    unfinished = next(
        action for action, button in window._more_pairs if button.objectName() == "unfinishedOpen"
    )
    assert unfinished.text().startswith("Unfinished")
