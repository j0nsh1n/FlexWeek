"""Month's date pane, first-row open, Sunday gutter, Large-text chips, and overdue through Unfinished."""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QFont, QFontMetrics
    from PySide6.QtTest import QSignalSpy, QTest
    from PySide6.QtWidgets import QAbstractButton, QApplication, QWidget

    from backend.month import build_month
    from desktop.native.hours.month import PANE_PX, MonthGrid, month_cells
    from desktop.native.tokens import text_knob, type_pt
    from desktop.native.widgets import OverlayBar
    from desktop.native.window import NativeWindow
    from desktop.tests.window_support import (  # noqa: F401
        qapp,
        server,
        settled,
        signed_out,
        wait_until,
        window,
    )


@pytest.fixture(scope="module")
def qapp_grid() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-month-pane-test"])


def september() -> dict:
    return build_month("2026-09", [], [])


def test_the_date_pane_has_the_study_time_switch_and_open_day(qapp_grid: QApplication) -> None:
    grid = MonthGrid()
    grid.resize(1280, 700)
    grid.set_month(september(), False, "2026-09-10")
    grid.show()
    qapp_grid.processEvents()
    assert grid.pane.load_switch.text() == "Show study time per date"
    assert grid.pane.open.text() == "Open Day"
    assert grid.pane.heading.text() == "Thursday 10 September"
    assert grid.overdue.isHidden()
    assert grid.overdue.text() == ""
    grid.pane.load_switch.setChecked(True)
    assert grid.canvas._show_load is True
    grid.close()


def test_the_date_pane_is_a_drawer_under_1150(qapp_grid: QApplication) -> None:
    grid = MonthGrid()
    grid.resize(1280, 700)
    grid.set_month(september(), False, "2026-09-10")
    grid.show()
    qapp_grid.processEvents()
    assert grid.width() >= 1150
    assert grid._split.indexOf(grid.pane) >= 0
    assert grid.pane.width() == PANE_PX
    grid.resize(1149, 700)
    qapp_grid.processEvents()
    assert grid.width() < 1150
    assert grid._split.indexOf(grid.pane) < 0
    assert grid.pane.parent() is grid
    assert grid.pane.geometry() == QRect(1149 - PANE_PX, grid.pane.y(), PANE_PX, grid.pane.height())
    # A drawer starts closed, so Saturday and Sunday are not under it.
    assert grid.pane.isHidden()
    click_date(qapp_grid, grid, "2026-09-12")
    assert grid.pane.isVisible()
    assert grid.pane.heading.text() == "Saturday 12 September"
    assert grid.pane.close_button.isVisible() and grid.pane.close_button.text() == "Close"
    QTest.keyClick(grid.pane, Qt.Key.Key_Escape)
    qapp_grid.processEvents()
    assert grid.pane.isHidden()
    click_date(qapp_grid, grid, "2026-09-13")
    grid.pane.close_button.click()
    qapp_grid.processEvents()
    assert grid.pane.isHidden()
    # Wide again, the pane is beside the grid and has nothing to close.
    grid.resize(1280, 700)
    qapp_grid.processEvents()
    assert grid._split.indexOf(grid.pane) >= 0
    assert grid.pane.isVisible() and grid.pane.close_button.isHidden()
    grid.close()


def click_date(qapp_grid: QApplication, grid: MonthGrid, iso: str) -> None:
    point = grid.canvas.mapFromGlobal(grid.canvas.cell_point(iso))
    QTest.mouseClick(grid.canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
    qapp_grid.processEvents()


def test_arrow_keys_move_the_date_and_enter_opens_it(qapp_grid: QApplication) -> None:
    grid = MonthGrid()
    grid.resize(1280, 700)
    grid.set_month(september(), False, "2026-09-10")
    grid.show()
    qapp_grid.processEvents()
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
    qapp_grid.processEvents()
    grid.canvas.setFocus()
    QTest.keyClick(grid.canvas, Qt.Key.Key_Right)
    assert grid.pane.isHidden()
    QTest.keyClick(grid.canvas, Qt.Key.Key_Return)
    qapp_grid.processEvents()
    assert grid.pane.isVisible() and grid.pane.heading.text() == "Friday 11 September"
    assert opened.count() == 1
    grid.close()


def test_another_weeks_homework_counts_as_study_time_and_ticks_only_when_done() -> None:
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


def test_sunday_never_sits_under_the_scroll_bar(qapp_grid: QApplication) -> None:
    grid = MonthGrid()
    grid.resize(900, 280)
    grid.set_month(september(), False, "2026-09-16")
    grid.show()
    qapp_grid.processEvents()
    assert grid.scroll.verticalScrollBar().maximum() > 0
    extra = OverlayBar.WIDE + OverlayBar.EDGE
    assert grid.canvas._bar_inset == extra
    sunday = grid.canvas.cell_rect(6)
    assert sunday.right() <= grid.canvas.width() - extra
    grid.close()


def test_a_chip_at_large_text_keeps_its_time_and_whole_words(qapp_grid: QApplication) -> None:
    grid = MonthGrid()
    font = QFont(grid.canvas.font())
    font.setPointSizeF(type_pt("body", "large"))
    grid.canvas.setFont(font)
    grid.resize(1280, 700)
    snapshot = september()
    for day in snapshot["days"]:
        if day["date"] == "2026-09-10":
            day["blocks"] = [
                {
                    "id": "read",
                    "title": "History essay reading",
                    "start": "08:00",
                    "duration_min": 60,
                }
            ]
    grid.set_month(snapshot, False, "2026-09-10")
    grid.show()
    qapp_grid.processEvents()
    assert text_knob(grid.canvas.font().pointSizeF()) == "large"
    assert grid.canvas._chip_lines() == 2
    words = "08:00 History essay reading"
    shown, _more = grid.canvas.chip_boxes(grid.canvas.index_of("2026-09-10"))
    box = shown[0][1]
    metrics = QFontMetrics(grid.canvas._small())
    elided = metrics.elidedText(words, Qt.TextElideMode.ElideRight, int(box.width() - 8))
    wrapped = metrics.boundingRect(
        QRect(0, 0, int(box.width() - 8), 400), int(Qt.TextFlag.TextWordWrap), words
    )
    assert elided != words
    assert wrapped.height() <= grid.canvas.chip_height() + 4
    assert grid.canvas.chip_words("read", "2026-09-10") == words
    grid.close()


def test_month_keeps_overdue_in_unfinished_not_on_a_status_strip(
    qapp: QApplication, window: NativeWindow
) -> None:
    window.resize(1280, 800)
    month = window.findChild(QAbstractButton, "viewMonth")
    month.click()
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
