"""Timeline's hours on Week: what a render, a tab or a new text size keeps, the zoom they open at, and
that every day can be reached by scrolling or by resting a block at the edge."""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import replace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

import shiboken6  # noqa: E402
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget  # noqa: E402

from desktop.native.layouts.timeline import TimelineView  # noqa: E402
from desktop.native.widgets import use_app_style  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.week.support_timeline import canvas, page_of, scene_of, scroll_of, shown  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-timeline-test"])
    use_app_style(application)
    yield application


def test_the_hours_are_kept_through_renders_and_tabs(qapp: QApplication) -> None:
    view = shown(qapp)
    week = scroll_of(view)
    week.zoom_by(1)
    view.show_week(replace(view.scene, minute=view.scene.minute + 1))
    view.show_week(replace(view.scene, surface="day"))
    day = scroll_of(view)
    view.show_week(replace(view.scene, surface="week"))
    qapp.processEvents()
    assert scroll_of(view) is week and week.px == 48
    assert day is not week and shiboken6.isValid(day) and not day.isVisible()


def test_parked_hours_die_with_the_window(qapp: QApplication) -> None:
    host = QWidget()
    view = TimelineView(host)
    QVBoxLayout(host).addWidget(view)
    view.show_week(scene_of("day"))
    host.show()
    qapp.processEvents()
    parked = scroll_of(view)
    view.show_week(scene_of("week"))
    assert shiboken6.isValid(parked) and not parked.isVisible()
    host.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not shiboken6.isValid(parked)


def test_the_week_opens_at_the_mock_ups_scale_and_not_at_a_level_kept_for_the_old_lines(
    qapp: QApplication,
) -> None:
    """0.16's lanes kept an hour's width across a line as `timeline.week`; opened as the columns'
    height it put the planner at twice its size."""
    view = TimelineView()
    view.remembered_zoom = {"timeline.week": 96}
    view.resize(1280, 744)
    view.show_week(scene_of())
    view.show()
    assert scroll_of(view).px == 36
    assert scroll_of(shown(qapp, "day")).px == 45


def test_a_new_text_size_makes_the_week_again_at_the_zoom_the_window_remembers(qapp: QApplication) -> None:
    view = shown(qapp)
    first = scroll_of(view)
    view.remembered_zoom = {"timeline.spread": 64}
    view.show_week(replace(view.scene, scale=1.25))
    qapp.processEvents()
    again = scroll_of(view)
    assert again is not first and again.px == 64


def test_zooming_out_stops_at_the_smallest_hour(qapp: QApplication) -> None:
    view = shown(qapp, size=(1280, 1400))
    scroll = scroll_of(view)
    scroll.zoom_by(-1)
    qapp.processEvents()
    assert scroll.px == 28


def test_a_week_taller_than_the_window_scrolls_and_every_day_can_be_reached(qapp: QApplication) -> None:
    view = shown(qapp, size=(1150, 300))
    page, hours = page_of(view), canvas(view)
    assert page.verticalScrollBar().maximum() > 0, "the pages are taller than the window"
    page.verticalScrollBar().setValue(page.verticalScrollBar().maximum())
    hours.reveal(6, 21 * 60, 22 * 60)
    qapp.processEvents()
    assert hours.in_view(6, 21 * 60) and hours.in_view(6, 22 * 60)
    hours.reveal(0, 7 * 60, 8 * 60)
    qapp.processEvents()
    assert hours.in_view(0, 7 * 60) and not hours.in_view(6, 22 * 60)


def test_a_block_rested_at_the_top_of_the_hours_scrolls_them_back(qapp: QApplication) -> None:
    """Inside the offscreen screen (800 by 800), where the hand can find what is under the pointer."""
    view = TimelineView()
    view.move(0, 0)
    view.resize(780, 560)
    view.show_week(scene_of())
    view.show()
    qapp.processEvents()
    hours, scroll = canvas(view), scroll_of(view)
    hours.reveal(3, 19 * 60, 20 * 60)
    qapp.processEvents()
    bar = scroll.verticalScrollBar()
    before = bar.value()
    assert before > 0
    grab = hours.block_rect("essay-1", 3).center()
    edge = QPoint(grab.x(), scroll.viewport().mapToGlobal(QPoint(0, 10)).y())

    def send(kind: QEvent.Type, at: QPoint, held: bool) -> None:
        buttons = Qt.MouseButton.LeftButton if held else Qt.MouseButton.NoButton
        local = QPointF(hours.mapFromGlobal(at))
        QApplication.sendEvent(
            hours,
            QMouseEvent(
                kind, local, QPointF(at), Qt.MouseButton.LeftButton, buttons, Qt.KeyboardModifier.NoModifier
            ),
        )

    send(QEvent.Type.MouseButtonPress, grab, True)
    for step in range(1, 9):
        send(QEvent.Type.MouseMove, grab + (edge - grab) * step / 8, True)
    wait_until(qapp, lambda: bar.value() < before, what="the hours scrolling back")
    view.hand.cancel()

