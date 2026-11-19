# ruff: noqa: F811
"""Material 3 in the real window: a refresh while Material is open stays on Material.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_material_window import material_window, qapp  # noqa: E402, F401
from desktop.tests.material_support import (  # noqa: E402
    pump,
    show_material,
)


def test_a_refresh_stays_on_material_and_does_not_take_the_plan_prompt(
    qapp: QApplication, material_window: NativeWindow
) -> None:
    trace = {"placed": [], "kept": "once"}
    session = material_window.session
    session.trace = trace
    session._fresh_plan = True
    root = show_material(qapp, material_window)
    assert root.objectName() == "materialShell"

    session.week_changed.emit()
    pump(qapp)

    assert material_window._stack.currentWidget().objectName() == "materialPage"
    assert session.consume_plan_review() == trace


def test_a_disposed_bridge_stops_following_the_week(
    qapp: QApplication, material_window: NativeWindow
) -> None:
    """dispose() cuts the session signal the bridge joined, so a week change after the drop reaches the
    bridge's own follower no more. The window's own follower is out of the way, since the window answers
    a week change through the page's publish, which refreshes directly."""
    show_material(qapp, material_window)
    bridge = material_window.findChild(QObject, "materialBridge")
    assert bridge is not None
    session = material_window.session
    reached: list[str] = []
    bridge.refresh = lambda: reached.append("refresh")
    session.week_changed.disconnect(material_window._on_week)

    bridge.dispose()
    session.week_changed.emit()
    pump(qapp)

    assert reached == []
