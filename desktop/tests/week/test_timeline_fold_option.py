# ruff: noqa: F811
"""Timeline's fold, moved on the page, is a Timeline option like the others: kept with the look and restored
when the app opens."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from desktop.native.layouts.registry import sanitize_layout  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    look_file,
    qapp,  # noqa: F401
    still,
    window,  # noqa: F401
)


def test_timelines_fold_is_kept_with_the_look_and_restored_on_open(
    qapp: QApplication, window: NativeWindow
) -> None:
    """A fold moved on the page is a Timeline option."""
    window._layout = {"main": "timeline", "day": "one", "options": {}}
    window._on_week()
    still(window)
    handle = window.planner.currentWidget().findChild(QWidget, "timelineFold")
    QTest.mouseClick(handle, Qt.MouseButton.LeftButton, pos=QPoint(handle.width() - 4, handle.height() // 2))
    qapp.processEvents()
    assert window._layout["options"] == {"timeline": {"fold": "4"}}
    assert json.loads(look_file().read_text())["layout"]["options"] == {"timeline": {"fold": "4"}}
    assert window.planner.currentWidget().findChild(QWidget, "timelineFold").text() == "‹ 4 | 3 ›"
    window._layout = sanitize_layout(None)
    window._load_look()
    window._on_week()
    qapp.processEvents()
    assert window._layout["options"]["timeline"]["fold"] == "4", "restored when the app opens"
    assert window.planner.currentWidget().findChild(QWidget, "timelineFold").text() == "‹ 4 | 3 ›"
