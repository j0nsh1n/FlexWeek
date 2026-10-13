"""Month's date pane, first-row open, Sunday gutter, Large-text chips, and the shared overdue strip."""

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
    from PySide6.QtWidgets import QAbstractButton, QApplication

    from backend.month import build_month
    from desktop.native.hours.month import PANE_PX, MonthGrid
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


def test_month_keeps_overdue_on_the_status_strip(qapp: QApplication, window: NativeWindow) -> None:
    window.resize(1280, 800)
    month = window.findChild(QAbstractButton, "viewMonth")
    month.click()
    wait_until(qapp, lambda: window.session.planner_view == "month")
    settled(qapp, window)
    assert window.status_strip.isVisible()
    assert window.status_overdue.text().endswith(" overdue")
    assert window.month_grid.overdue.isHidden()
    assert window.month_grid.overdue.text() == ""
