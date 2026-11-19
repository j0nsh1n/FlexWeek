"""The due date in the homework editor: new homework is due tomorrow whatever week is on screen, and
changing the due date turns off what acts on the saved homework. The date's calendar month is a picture:
screens_sheets_h7.py."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QDate, QTime
from PySide6.QtWidgets import QApplication

from desktop.native.widgets import DueField
from desktop.tests.sheets.support_plan import opened_with, thursday_iso, window  # noqa: F401
from desktop.tests.window_support import qapp  # noqa: F401


def test_a_due_field_says_it_changed_with_no_arguments(qapp: QApplication) -> None:  # noqa: F811
    field = DueField("2026-09-24", "probe")
    heard: list[tuple] = []
    field.changed.connect(lambda *args: heard.append(args))
    field.date.setDate(QDate(2026, 9, 25))
    field.timed.setChecked(True)
    field.time.setTime(QTime(8, 15))
    assert heard == [(), (), ()]
