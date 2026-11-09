"""Text size makes the Material Week and Day hour rows bigger, also for a student who zoomed the
hours before. How much bigger is a picture (desktop/tests/pictures); here only that it grows, by the
text size's factor, and that zoom keeps stepping through its own levels."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import pump
from desktop.tests.week.support_material_page import fresh_material


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-rows-grow-with-text"])


def _text_size(bridge: object, size: str) -> None:
    bridge.showPage("settings")
    pump(QApplication.instance(), 5)
    bridge._settings_bridge.setTextSize(size)
    pump(QApplication.instance(), 10)


@pytest.mark.parametrize("screen,row", [("week", "hourRow"), ("day", "dayHourRow")])
def test_a_zoomed_hour_row_still_grows_with_the_text_size(
    qapp: QApplication, window: NativeWindow, screen: str, row: str
) -> None:
    fresh_material(qapp, window)
    bridge = window._material_page.bridge
    bridge.showPage(screen)
    pump(qapp, 5)
    bridge.zoomBy(1)
    pump(qapp, 5)
    zoomed = int(bridge.property(row))
    assert zoomed == 72

    _text_size(bridge, "larger")
    bridge.showPage(screen)
    pump(qapp, 10)
    assert int(bridge.property(row)) == round(72 * 1.6)

    _text_size(bridge, "large")
    bridge.showPage(screen)
    pump(qapp, 10)
    assert int(bridge.property(row)) == round(72 * 1.3)

    _text_size(bridge, "normal")
    bridge.showPage(screen)
    pump(qapp, 10)
    assert int(bridge.property(row)) == zoomed


def test_zoom_keeps_its_levels_at_a_larger_text_size(qapp: QApplication, window: NativeWindow) -> None:
    """At Larger text a zoom step still moves one level (56 -> 72 -> 96), drawn 1.6 times as tall, and
    the zoom buttons follow the level, not the drawn height."""
    fresh_material(qapp, window)
    bridge = window._material_page.bridge
    _text_size(bridge, "larger")
    bridge.showPage("week")
    pump(qapp, 10)
    assert int(bridge.property("hourRow")) == round(56 * 1.6)
    bridge.zoomBy(1)
    pump(qapp, 5)
    assert int(bridge.property("hourRow")) == round(72 * 1.6)
    bridge.zoomBy(1)
    pump(qapp, 5)
    assert int(bridge.property("hourRow")) == round(96 * 1.6)
    bridge.zoomBy(-2)
    pump(qapp, 5)
    assert int(bridge.property("hourRow")) == round(56 * 1.6)
    assert bridge.property("canZoomIn") is True
    assert bridge.property("canZoomOut") is True
