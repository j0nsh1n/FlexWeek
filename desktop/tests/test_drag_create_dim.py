"""A drag-created sheet must not refresh the week before its dim appears."""

from __future__ import annotations

from dataclasses import replace

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QWidget

from desktop.native.hours.canvas import HoursCanvas
from desktop.native.hours.hand import Gesture
from desktop.native.layouts.base import LayoutView
from desktop.native.motion import apply_ui_effects
from desktop.native.widgets import BlockDialog, HomeworkDialog, SheetShade
from desktop.native.window import ClassicWeek, NativeWindow
from desktop.tests.test_drag_results import LEFT, minute, settled, wait_until

pytest_plugins = ("desktop.tests.test_drag_results",)


def drag(qapp: QApplication, hours: HoursCanvas, day: int, start: int, end: int) -> None:
    start_point = hours.point_for(day, start) + QPoint(0, 2)
    end_point = hours.point_for(day, end)
    QTest.mousePress(hours, LEFT, pos=start_point)
    for step in range(1, 9):
        point = start_point + (end_point - start_point) * step / 8
        QTest.mouseMove(hours, point)
    QTest.mouseRelease(hours, LEFT, pos=end_point)


def cancel(dialog) -> int:
    dialog.show()
    buttons = dialog.findChild(QDialogButtonBox, "dialogButtons")
    QTest.mouseClick(buttons.button(QDialogButtonBox.StandardButton.Cancel), LEFT)
    return dialog.result()


def test_drag_create_clears_preview_without_refreshing_week_before_dim(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    apply_ui_effects("normal")
    counts = {"set_week": 0}
    release_count: int | None = None
    refreshed_before_dim: list[bool] = []
    original_set_week = ClassicWeek.set_week
    original_release = window.hand._released
    original_show_event = SheetShade.showEvent

    def set_week(self, *args, **kwargs):
        if self is window.week_table:
            counts["set_week"] += 1
        return original_set_week(self, *args, **kwargs)

    def released():
        nonlocal release_count
        release_count = counts["set_week"]
        return original_release()

    def shade_show_event(shade: SheetShade, event) -> None:
        if shade.parentWidget() is window and release_count is not None:
            refreshed_before_dim.append(counts["set_week"] != release_count)
        original_show_event(shade, event)

    monkeypatch.setattr(ClassicWeek, "set_week", set_week)
    monkeypatch.setattr(window.hand, "_released", released)
    monkeypatch.setattr(SheetShade, "showEvent", shade_show_event)
    monkeypatch.setattr(BlockDialog, "exec", cancel)

    hours = window.week_table.hours
    start, end = minute("16:00"), minute("17:00")
    hours.reveal(3, start - 60, end + 60)
    qapp.processEvents()
    before = list(window.session.blocks)
    release_count = None
    drag(qapp, hours, 3, start, end)
    wait_until(qapp, lambda: release_count is not None and not window.hand.busy)
    assert window.hand.preview is None, "the drag ghost is cleared before the sheet is shown"
    settled(qapp, window)
    assert refreshed_before_dim and not any(refreshed_before_dim), (
        "the week refreshed after release but before the dim"
    )
    assert window.session.blocks == before, "Cancel leaves the week model unchanged"
    assert not any(item.get("start") == "16:00" and item.get("days") == [3] for item in window.session.blocks)

    release_count = None
    before_add = counts["set_week"]
    monkeypatch.setattr(HomeworkDialog, "exec", cancel)
    window.findChild(QWidget, "addButton").click()
    qapp.processEvents()
    assert counts["set_week"] == before_add, "opening Add does not refresh the week"
    assert window.session.blocks == before, "the Add-button control leaves the week model unchanged"


def test_create_release_keeps_a_scene_that_arrived_during_the_hold(
    qapp: QApplication, window: NativeWindow
) -> None:
    view = window._layout_view("timeline")
    assert isinstance(view, LayoutView) and view.scene is not None
    arrived = replace(view.scene, minute=view.scene.minute + 1)
    view.hold(True)
    view.show_week(arrived)
    assert view._held is arrived

    window.hand._release_kind = Gesture.CREATE
    try:
        window._hold_renders(False)
    finally:
        window.hand._release_kind = None

    assert view.scene is arrived, "release shows the latest scene before skipping the classic refresh"
    qapp.processEvents()
    assert view.scene is arrived, "the deferred refresh does not replace the held scene"
