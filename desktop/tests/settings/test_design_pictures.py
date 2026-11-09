"""The pictures of each design in setup and Settings are built and freed whole, and the sample week files
Soccer under Sports. How the Today's app picture is coloured in High contrast is judged on the pictures
in pictures/screens_settings_h2.py."""

from __future__ import annotations

import gc

import pytest
from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from desktop.native.previews import render, sample_week
from desktop.tests.window_support import qapp  # noqa: F401


@pytest.mark.parametrize("main", ["classic", "timeline"])
def test_a_picture_leaves_nothing_alive_for_the_garbage_collector(qapp: QApplication, main: str) -> None:  # noqa: F811
    """A Qt object left alive in a reference cycle is freed whenever Python's collector next runs,
    which can be in the middle of painting the window. In the rig that hung the app. Whatever a picture
    builds is gone once it is drawn, not waiting for the collector."""
    gc.collect()
    gc.set_debug(gc.DEBUG_SAVEALL)
    try:
        picture = render(main, None, "system", None, 240)
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        gc.collect()
        alive = [
            f"{type(item).__name__} {item.objectName()!r}"
            for item in gc.garbage
            if isinstance(item, QObject) and isValid(item)
        ]
    finally:
        gc.set_debug(0)
        gc.garbage.clear()
        gc.collect()
    assert not picture.isNull()
    assert alive == []


def test_the_preview_week_puts_soccer_in_sports() -> None:
    _monday, blocks, _homework = sample_week()
    soccer = next(block for block in blocks if block["id"] == "soccer")
    assert soccer["category"] == "exercise"
