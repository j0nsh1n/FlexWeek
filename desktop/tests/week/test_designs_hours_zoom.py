"""How close the hours are, kept for this device: Today's app and any design that draws hours of its own
open them at the level the student last chose, and a redraw does not take it back."""

# ruff: noqa: E402, F811  (pytest fixtures imported by name)
from __future__ import annotations

import contextlib
import json
from collections.abc import Callable

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractButton, QApplication, QPushButton, QVBoxLayout, QWidget

from desktop.native.hours.canvas import BlockPainter, HoursCanvas
from desktop.native.hours.hand import Hand
from desktop.native.hours.zoom import HoursScroll, Scale
from desktop.native.layouts.base import LayoutView, Scene, empty
from desktop.native.layouts.views import VIEW_CLASSES
from desktop.native.look import resolved_palette
from desktop.native.window import NativeWindow
from desktop.tests.light_app import ORIGIN, open_light  # noqa: F401
from desktop.tests.week.support_design_plan import SIZE, plan_week, settled, use
from desktop.tests.window_support import free, look_file, qapp  # noqa: F401


@pytest.fixture()
def window(qapp: QApplication, open_light: Callable[..., NativeWindow]) -> NativeWindow:
    """School, the History essay and an unplaced Math worksheet, with the clock held on Thursday 10:00."""
    return plan_week(qapp, open_light(SIZE))


def another_window() -> NativeWindow:
    """A second window on the same device: it reads what the first one kept in the look file."""
    return NativeWindow(ORIGIN)


def close_another(window: NativeWindow) -> None:
    # Closed and deleted here, so nothing of this second window runs during a later test.
    with contextlib.suppress(RuntimeError):
        window.session.client.reset()
    window.close()
    free(window)


def test_how_close_the_hours_are_is_kept_for_this_device(qapp: QApplication, window: NativeWindow) -> None:
    """A zoom chosen on Week is in the look file, and the next window opens the Week at it."""
    window.findChild(QAbstractButton, "viewWeek").click()
    qapp.processEvents()
    QTest.mouseClick(window.findChild(QPushButton, "weekZoomIn"), Qt.MouseButton.LeftButton)
    assert window.week_table.scroll.px == 64
    assert json.loads(look_file().read_text())["zoom"] == {"classic.week": 64}
    again = another_window()
    try:
        assert again.week_table.scroll.px == 64
        assert again.day_view.scroll.px == 96, "the Day was not zoomed, so it opens at its own level"
    finally:
        close_another(again)


class ZoomingDesign(LayoutView):
    """The least a design with hours of its own does: hours that scroll and zoom, made anew on every
    render, as a design that rebuilds its page does."""

    layout_id = "mission"

    def __init__(self, parent: QWidget | None = None, *, hand: Hand | None = None) -> None:
        super().__init__(parent, hand=hand)
        self._box = QVBoxLayout(self)
        self.scroll: HoursScroll | None = None

    def render(self, scene: Scene, week_changed: bool) -> None:
        empty(self._box)
        hours = HoursCanvas(self.hand, BlockPainter(resolved_palette("system", False, None)))
        hours.set_week(scene.week.occurrences, scene.today, scene.minute)
        scale = Scale("test.hours", (32, 48, 64, 96), 48)
        self.scroll = self.keep_zoom(HoursScroll(hours, scale, lambda px: 24 * px, name="test", gutter=48))
        self._box.addWidget(self.scroll)


def zooming_design(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> ZoomingDesign:
    """The test design, where a real design goes: chosen as the main view, in Mission's place."""
    monkeypatch.setitem(VIEW_CLASSES, "mission", ZoomingDesign)
    view = use(qapp, window, "mission")
    assert isinstance(view, ZoomingDesign)
    return view


def zoom_in(view: ZoomingDesign) -> None:
    assert view.scroll is not None
    QTest.mouseClick(view.scroll.buttons.into, Qt.MouseButton.LeftButton)


def redrawn(qapp: QApplication, window: NativeWindow) -> None:
    """A real change, saved: the design draws a new scene, as it does after any edit."""
    window.session.add_block(
        {
            "id": "club",
            "title": "Club",
            "kind": "locked",
            "category": "extra",
            "start": "18:00",
            "duration_min": 60,
            "days": [5],
        }
    )
    window.session.save()
    settled(qapp, window)


def test_a_designs_zoom_is_kept_under_its_own_key(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    view = zooming_design(qapp, window, monkeypatch)
    zoom_in(view)
    assert view.scroll is not None and view.scroll.px == 64
    assert json.loads(look_file().read_text())["zoom"] == {"test.hours": 64}


def test_hours_a_design_makes_again_open_at_the_level_just_chosen(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The hours made on the next render open where the student left the last ones, not where the
    design first opened."""
    view = zooming_design(qapp, window, monkeypatch)
    zoom_in(view)
    zoomed = view.scroll
    redrawn(qapp, window)
    assert view.scroll is not zoomed, "the save drew new hours"
    assert view.scroll is not None and view.scroll.px == 64


def test_a_new_window_opens_a_designs_hours_at_the_remembered_level(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    view = zooming_design(qapp, window, monkeypatch)
    zoom_in(view)
    again = another_window()
    try:
        # The window reads the look file as it opens; the design it makes later takes the level.
        shown = again._layout_view("mission")
        assert isinstance(shown, ZoomingDesign) and shown.scroll is not None
        assert shown.scroll.px == 64
    finally:
        close_another(again)


def test_a_design_that_never_zooms_leaves_the_kept_levels_alone(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    window.findChild(QAbstractButton, "viewWeek").click()
    qapp.processEvents()
    QTest.mouseClick(window.findChild(QPushButton, "weekZoomIn"), Qt.MouseButton.LeftButton)
    view = zooming_design(qapp, window, monkeypatch)
    redrawn(qapp, window)
    assert view.scroll is not None and view.scroll.px == 48
    assert json.loads(look_file().read_text())["zoom"] == {"classic.week": 64}
