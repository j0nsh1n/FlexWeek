"""How close the hours are, kept for this device: Today's app opens them at the level the student last chose,
and a redraw does not take it back."""

# ruff: noqa: E402, F811  (pytest fixtures imported by name)
from __future__ import annotations

import contextlib
import json
from collections.abc import Callable

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractButton, QApplication, QPushButton

from desktop.native.window import NativeWindow
from desktop.tests.light_app import ORIGIN, open_light  # noqa: F401
from desktop.tests.week.support_design_plan import SIZE, plan_week
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
