"""Bento keeps each surface's scroll and zoom through a redraw, and frees them with the view."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

import shiboken6  # noqa: E402
from PySide6.QtCore import QCoreApplication, QEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.layouts.bento import DAY_SCALE  # noqa: E402
from desktop.tests.day.support_bento import scene, shown  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-bento-zoom-test"])


def test_day_and_week_keep_their_scroll_and_zoom_through_redraw(qapp: QApplication) -> None:
    view = shown(qapp)
    week = view._scrolls["week"]
    week.zoom_by(1)
    week_px = week.px
    week.verticalScrollBar().setValue(260)
    view.show_week(scene("week", clock="13:41"))
    qapp.processEvents()
    assert view._scrolls["week"] is week
    assert week.px == week_px
    assert week.verticalScrollBar().value() > 0
    view.show_week(scene("day"))
    qapp.processEvents()
    day = view._scrolls["day"]
    day.zoom_by(1)
    view.show_week(scene("week", clock="13:42"))
    qapp.processEvents()
    assert view._scrolls["week"] is week
    assert view._scrolls["day"] is day
    assert week.px == week_px
    view.show_week(scene("day", clock="13:43"))
    qapp.processEvents()
    assert view._scrolls["day"] is day
    assert day.px == DAY_SCALE.step(DAY_SCALE.default, 1)
    view.show_week(scene("month"))
    qapp.processEvents()
    assert view.hours_surfaces() == []
    assert view.month_surfaces()
    assert shiboken6.isValid(week)
    assert shiboken6.isValid(day)
    view.close()
    view.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not shiboken6.isValid(week)
    assert not shiboken6.isValid(day)
