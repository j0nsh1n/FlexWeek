"""The homework form's due date steps with the arrow keys by a day and with Page Up and Down by a week."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QDate, Qt
from PySide6.QtTest import QTest

from desktop.native.widgets import HomeworkDialog
from desktop.tests.window_support import qapp  # noqa: F401


def test_homework_due_date_keys_step_by_day_and_by_week(qapp) -> None:  # noqa: F811
    dialog = HomeworkDialog(None, today="2026-10-05")
    field = dialog.due.date
    field.setDate(QDate(2026, 10, 9))
    field.setFocus()

    QTest.keyClick(field, Qt.Key.Key_Up)
    assert field.date() == QDate(2026, 10, 10)
    QTest.keyClick(field, Qt.Key.Key_Up)
    assert field.date() == QDate(2026, 10, 11)
    QTest.keyClick(field, Qt.Key.Key_PageDown)
    assert field.date() == QDate(2026, 10, 18)
    QTest.keyClick(field, Qt.Key.Key_Down)
    assert field.date() == QDate(2026, 10, 17)
