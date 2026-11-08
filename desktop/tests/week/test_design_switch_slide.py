"""Switching design with the Agenda rail coming or going hides the rail by sliding the new design in, and
the slide ends on the new design's page with its pictures put away. How the slid-in picture compares with
the page it lands on is judged in the picture review, not here."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QEvent, QStandardPaths  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from desktop.native import motion  # noqa: E402
from desktop.native import window as window_module  # noqa: E402
from desktop.native.layouts.registry import sanitize_layout  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import window  # noqa: E402, F401
from desktop.tests.test_week_side import seeded  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-design-switch-test"])


@pytest.mark.parametrize("design", ["mission", "timeline", "bento", "clay", "retro"])
def test_switching_design_slides_it_in_and_the_slide_ends_on_the_new_page(
    qapp: QApplication,
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    design: str,
) -> None:
    seeded(qapp, window)
    window._motion = "normal"
    # As Settings applies a design: kept, then the week shown again.
    window._layout = sanitize_layout({"main": "classic", "day": "one"})
    window._save_look()
    window._on_week()
    wait_until(qapp, lambda: window.rail.isVisible(), what="the rail showing on Today's app")
    slid: list[bool] = []
    original = window_module.slide_view

    def slide_view(host, picture, live, level, *, back=False):
        original(host, picture, live, level, back=back)
        slid.append(any(child.isVisible() for child in host.findChildren(QLabel, motion.SLIDE_NAME)))

    monkeypatch.setattr(window_module, "slide_view", slide_view)
    window._layout = sanitize_layout({"main": design, "day": "one"})
    window._save_look()
    window._on_week()
    assert slid and slid[0], f"switching to {design} hid the rail without sliding"
    motion.settle(window.planner)
    wait_until(qapp, lambda: window.planner.currentWidget() is window._views[design])

    def pictures_put_away() -> bool:
        # The slide's pictures are put away with deleteLater, which processEvents alone never runs.
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        return not any(label.isVisible() for label in window.findChildren(QLabel, motion.SLIDE_NAME))

    wait_until(qapp, pictures_put_away, what="the slide's pictures put away")
