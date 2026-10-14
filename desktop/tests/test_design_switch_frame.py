"""Switching design with the Agenda rail coming or going slides the new design in as a picture. That
picture is the design as it lands, so nothing snaps into another place when the slide ends (Jonathan,
1.0.0: parts "suddenly change" as a design loads). Without the layout pass before the picture, Mission
slid in 7% different from where it landed."""

from __future__ import annotations

import importlib.util

import pytest

pytestmark = pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="needs PySide6")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QLabel

    from desktop.native import motion
    from desktop.native import window as window_module
    from desktop.native.layouts.registry import sanitize_layout
    from desktop.tests.test_hours_open import qapp, wait_until, window  # noqa: F401
    from desktop.tests.test_week_side import seeded


def _differing_share(first: QImage, second: QImage) -> float:
    first = first.convertToFormat(QImage.Format.Format_RGB32)
    second = second.convertToFormat(QImage.Format.Format_RGB32)
    assert first.size() == second.size()
    step = 4
    seen = differ = 0
    for y in range(0, first.height(), step):
        for x in range(0, first.width(), step):
            seen += 1
            a, b = first.pixel(x, y), second.pixel(x, y)
            if max(abs(((a >> s) & 255) - ((b >> s) & 255)) for s in (0, 8, 16)) > 24:
                differ += 1
    return differ / seen


@pytest.mark.parametrize("design", ["mission", "timeline", "bento", "clay", "retro"])
def test_the_design_sliding_in_is_pictured_as_it_lands(qapp, window, monkeypatch, design) -> None:  # noqa: F811
    seeded(qapp, window)
    window._motion = "normal"
    # As Settings applies a design: kept, then the week shown again.
    window._layout = sanitize_layout({"main": "classic", "day": "one"})
    window._save_look()
    window._on_week()
    for _ in range(5):
        qapp.processEvents()
    assert window.rail.isVisible()
    taken: list[tuple[QImage, object]] = []
    original = window_module.slide_view

    def slide_view(host, picture, live, level, *, back=False):
        original(host, picture, live, level, back=back)
        moving = next(
            child for child in host.findChildren(QLabel, motion.SLIDE_NAME) if child.isVisible()
        )
        taken.append((moving.pixmap().toImage(), picture.geometry()))

    monkeypatch.setattr(window_module, "slide_view", slide_view)
    window._layout = sanitize_layout({"main": design, "day": "one"})
    window._save_look()
    window._on_week()
    assert taken, f"switching to {design} hid the rail without sliding"
    coming, area = taken[0]
    motion.settle(window.planner)
    for _ in range(10):
        qapp.processEvents()
        # The slide's pictures are put away with deleteLater, which processEvents alone never runs.
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert window.planner.currentWidget() is window._views[design]
    landed = window._week_page.grab(area).toImage()
    share = _differing_share(coming.scaled(landed.size()), landed)
    assert share < 0.02, f"{design}: {share:.1%} of the picture that slid in differs from where it landed"
