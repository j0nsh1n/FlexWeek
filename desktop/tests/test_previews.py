"""The pictures of each design in setup and Settings."""

from __future__ import annotations

import gc
import importlib.util
import os
from collections.abc import Iterator

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QEvent, QObject
    from PySide6.QtWidgets import QApplication
    from shiboken6 import isValid

    from desktop.native.previews import render


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-previews-test"])


@pytest.mark.parametrize("main", ["classic", "timeline"])
def test_a_picture_leaves_nothing_alive_for_the_garbage_collector(qapp: QApplication, main: str) -> None:
    """A Qt object left alive in a reference cycle is freed whenever Python's collector next runs,
    which can be in the middle of painting the window. In the rig that hung the app. Whatever a
    picture builds is gone once it is drawn, not waiting for the collector."""
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
