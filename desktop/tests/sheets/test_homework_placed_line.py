"""Edit homework says where the homework is placed: the days it has times on, when it is due, and how
many times when it is more than one. Add homework and homework with no time yet say nothing."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QWidget

from desktop.native.widgets import HomeworkDialog
from desktop.tests.sheets.support_homework import essay, host, opened, session
from desktop.tests.window_support import free, qapp  # noqa: F401


def test_edit_says_where_the_homework_is_placed(qapp: QApplication) -> None:  # noqa: F811
    parent = host(session(4, "15:30"))
    dialog = opened(parent, essay())
    line = dialog.placed_line
    assert line.isVisible() and line.text() == "Planned Fri 18 · due Fri 25"
    free(dialog)
    free(parent)


def test_edit_counts_every_time_it_is_placed(qapp: QApplication) -> None:  # noqa: F811
    parent = host(
        session(5, "10:00"), session(4, "15:30"), session(2, None), session(1, "09:00", completed=True)
    )
    dialog = opened(parent, essay())
    assert dialog.placed_line.text() == "Planned Fri 18 and Sat 19 · due Fri 25 · 2 times"
    free(dialog)
    free(parent)


def _dialog_in_week_of_12_october(*blocks: dict) -> tuple[QWidget, HomeworkDialog]:
    parent = QWidget()
    parent.session = SimpleNamespace(  # type: ignore[attr-defined]
        now_ms=lambda: int(datetime(2026, 10, 12, 12, 0).timestamp() * 1000),
        blocks=list(blocks),
        week_start="2026-10-12",
    )
    dialog = HomeworkDialog(parent, essay(due="2026-10-21"), "2026-10-12")
    dialog.show()
    QApplication.processEvents()
    return parent, dialog


def test_the_placed_line_names_the_days_and_the_due_in_another_week(qapp: QApplication) -> None:  # noqa: F811
    parent, two = _dialog_in_week_of_12_october(session(4, "15:30"), session(5, "10:00"))
    assert two.placed_line.text() == "Planned Fri 16 and Sat 17 · due Wed 21 · 2 times"
    free(two)
    free(parent)
    other, one = _dialog_in_week_of_12_october(session(4, "15:30"))
    assert one.placed_line.text() == "Planned Fri 16 · due Wed 21"
    free(one)
    free(other)


def test_nothing_is_said_when_it_is_not_placed_or_new(qapp: QApplication) -> None:  # noqa: F811
    parent = host(session(2, None))
    unplaced = opened(parent, essay())
    assert not unplaced.placed_line.isVisible()
    free(unplaced)
    free(parent)
    other = host(session(4, "15:30"))
    new = opened(other)
    assert not new.placed_line.isVisible()
    free(new)
    free(other)
