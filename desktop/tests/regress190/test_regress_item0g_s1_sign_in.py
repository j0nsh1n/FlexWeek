"""Regression for QA's S1 (fix-specs-0190.md): a time box's problem line is a row in the layout and
covers no other control. The sign-in and setup parts went with the Widgets pages (1.5.0).

Keys and clicks go through the window system. Known failures are xfail(strict=True).
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLineEdit, QWidget

import desktop.native.window as window_module
from desktop.native.fields import ProblemLine
from desktop.tests.window_support import qapp, server, signed_out  # noqa: F401


@pytest.fixture()
def alerts(monkeypatch):
    said: list[tuple[str, bool]] = []
    real = window_module.announce

    def spy(widget, words, *, assertive=False):
        said.append((words, assertive))
        return real(widget, words, assertive=assertive)

    monkeypatch.setattr(window_module, "announce", spy)
    return said


# 0g: Sign in -------------------------------------------------------------------------------------


# 0g: Reset password ------------------------------------------------------------------------------


# 0g: 810 px with Large text ----------------------------------------------------------------------


# S1 ----------------------------------------------------------------------------------------------


def covered_by_problem(top: QWidget, field: QWidget) -> list[str]:
    from PySide6.QtWidgets import QAbstractButton, QAbstractSpinBox, QComboBox

    lines = [line for line in top.findChildren(ProblemLine) if line.isVisible() and line.field is field]
    assert lines, "no problem line shown"
    area = QRect(lines[0].mapTo(top, QPoint(0, 0)), lines[0].size())
    hit = []
    for other in top.findChildren(QWidget):
        mine = other is field or field.isAncestorOf(other) or lines[0].isAncestorOf(other)
        inner = isinstance(other.parentWidget(), (QAbstractSpinBox, QComboBox))
        control = isinstance(other, (QLineEdit, QAbstractSpinBox, QComboBox, QAbstractButton)) and not inner
        if other.isVisible() and not mine and control and area.intersects(
            QRect(other.mapTo(top, QPoint(0, 0)), other.size())
        ):
            hit.append(other.objectName() or type(other).__name__)
    return hit


def test_s1_block_editor_starts_problem_does_not_cover_end(qapp) -> None:
    """A passing guard on 0.19.0 (S1 acceptance): no control under the line."""
    from desktop.native.widgets import BlockDialog
    from desktop.tests.regress184.test_regress_item0_time_boxes import _up, enter
    from desktop.tests.window_support import free

    dialog = BlockDialog(None, day=1, start="16:00", duration_min=60)
    _up(qapp, dialog)
    try:
        enter(dialog.start, "tab-in")
        for char in "99":
            QTest.keyClick(dialog.windowHandle(), char)
        QTest.keyClick(dialog.windowHandle(), Qt.Key.Key_Tab)
        qapp.processEvents()
        assert covered_by_problem(dialog, dialog.start) == []
    finally:
        QTest.qWait(20)
        dialog.hide()
        free(dialog)
