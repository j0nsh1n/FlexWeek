# ruff: noqa: F811
"""Add homework asks one question at a time: Due shows after What has a title, and Estimated time after
that. (That the sheet is tall enough to read is a picture: sheets.add_homework_sheet.)"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.widgets import HomeworkDialog  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    go_length,
    go_when,
    qapp,  # noqa: F401
    window,  # noqa: F401
)


def test_add_homework_shows_its_questions_in_turn(qapp: QApplication, window: NativeWindow) -> None:
    homework = HomeworkDialog(window)
    homework.show()
    qapp.processEvents()
    assert homework.title.isVisibleTo(homework)
    assert not homework.due.isVisibleTo(homework)
    assert not homework.estimate.isVisibleTo(homework)
    go_when(homework)
    assert homework.due.isVisibleTo(homework)
    go_length(homework)
    assert homework.estimate.isVisibleTo(homework)
    homework.close()
