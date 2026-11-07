"""The homework form asks for a type, not a priority, and calls a fixed time "pinned".

Expected words come from the 0.19.0 wording audit (findings 5 and 7), not from the code's output.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QTime
from PySide6.QtWidgets import QApplication, QLabel

from desktop.native.widgets import HomeworkDialog
from desktop.tests.sheets.support_clock_typing import twelve_hour_clock  # noqa: F401
from desktop.tests.window_support import free, qapp  # noqa: F401


def test_the_homework_form_asks_for_a_type_not_a_priority(qapp: QApplication) -> None:  # noqa: F811
    dialog = HomeworkDialog(None, None, "2026-10-12")
    box = dialog.priority
    assert [box.itemText(i) for i in range(box.count())] == [
        "Test prep",
        "Quiz prep",
        "Everyday homework",
        "Reading",
    ]
    said = [label.text() for label in dialog.findChildren(QLabel)]
    assert "Type" in said and "Priority" not in said
    assert "Tests are planned first, then quizzes, then everyday homework, then reading." in said
    free(dialog)


@pytest.mark.usefixtures("twelve_hour_clock")
def test_do_it_at_says_pinned_in_the_clock_the_account_uses(qapp: QApplication) -> None:  # noqa: F811
    dialog = HomeworkDialog(None, None, "2026-10-12")
    dialog.show()
    dialog.when.setCurrentIndex(1)
    dialog.when_day.set_days([3])
    dialog.when_time.setTime(QTime(17, 0))
    assert dialog.when_note.text() == "Pinned to Thu at 5:00 PM. Plan won't move it."
    free(dialog)
