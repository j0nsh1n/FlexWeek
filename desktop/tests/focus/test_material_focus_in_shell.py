# ruff: noqa: F811
"""Focus is a screen inside Material 3: the page stays Material's, Back closes the screen, and a refresh
while it is open keeps it open and keeps the plan prompt for after.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_material_window import material_window, qapp  # noqa: E402, F401
from desktop.tests.material_support import pump, qml, show_material  # noqa: E402


def test_focus_back_returns_to_material(qapp: QApplication, material_window: NativeWindow) -> None:
    window = material_window
    root = show_material(qapp, window)
    window._open_focus_screen()
    pump(qapp)
    focus = window._material_page.bridge.focus

    assert window._stack.currentWidget().objectName() == "materialPage"
    assert focus.open
    assert qml(root, "materialFocus").property("visible") is True
    focus.back()
    pump(qapp)
    assert not focus.open
    assert window._stack.currentWidget().objectName() == "materialPage"


def test_a_refresh_with_focus_open_keeps_focus_and_the_plan_prompt(
    qapp: QApplication, material_window: NativeWindow
) -> None:
    window = material_window
    trace = {"placed": [], "kept": "focus"}
    window.session.trace = trace
    window.session._fresh_plan = True
    show_material(qapp, window)
    window._open_focus_screen()

    window.session.week_changed.emit()
    pump(qapp)

    focus = window._material_page.bridge.focus
    assert window._stack.currentWidget().objectName() == "materialPage"
    assert focus.open
    assert window.plan_review.isHidden()
    assert window.session._fresh_plan is True
    focus.back()
    pump(qapp)
    assert not focus.open
    assert window.session.consume_plan_review() == trace
