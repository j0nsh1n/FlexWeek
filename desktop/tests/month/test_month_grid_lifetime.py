"""A month grid with no window around it is freed when it is let go, without waiting for the garbage
collector."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.hours.month import MonthGrid  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-month-lifetime-test"])


def test_a_month_with_no_window_is_freed_without_the_garbage_collector(qapp: QApplication) -> None:
    """A month drawn with no window gets a hand of its own. That hand once kept a reference back to
    the month, a cycle only the garbage collector could free, at a moment of its choosing."""
    import gc
    import weakref

    gc.collect()
    # The run keeps the collector off (conftest); put back whatever was set, never switch it on.
    was_on = gc.isenabled()
    gc.disable()
    try:
        grid = MonthGrid()
        gone = weakref.ref(grid)
        del grid
        assert gone() is None
    finally:
        if was_on:
            gc.enable()
