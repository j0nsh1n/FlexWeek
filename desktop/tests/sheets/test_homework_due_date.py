"""The due date in the homework editor: new homework is due tomorrow whatever week is on screen, and
changing the due date turns off what acts on the saved homework. The date's calendar month is a picture:
screens_sheets_h7.py."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QDate, QTime
from PySide6.QtWidgets import QApplication, QDialog, QPushButton

from desktop.native.widgets import DueField, HomeworkDialog
from desktop.native.window import NativeWindow
from desktop.tests.sheets.support_plan import opened_with, thursday_iso, window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_new_homework_opens_due_tomorrow_whatever_week_is_on_screen(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dues: list[str] = []

    def look(dialog: HomeworkDialog) -> int:
        dues.append(dialog.due.value())
        return QDialog.DialogCode.Rejected

    opened_with(monkeypatch, look)
    window._add_homework()
    tomorrow = (date.fromisoformat(thursday_iso(window)) + timedelta(days=1)).isoformat()
    assert dues == [tomorrow], "tomorrow, not on the Monday of the week on screen"

    dues.clear()
    window._edit_homework("math")
    assert dues == [window.session.assignments["math"]["due"][:10]], "editing keeps its own due date"

    ahead = (date.fromisoformat(window.session.week_start) + timedelta(days=7)).isoformat()
    window.session.load_week(ahead)
    wait_until(qapp, lambda: window.session.week_start == ahead and not window.session.busy)
    window._add_homework()
    assert dues[-1] == tomorrow


def test_changing_the_due_date_turns_off_what_acts_on_the_saved_homework(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Let FlexWeek move it acts on the saved homework, so an unsaved edit turns it off. The due date's
    signal handed a date to a signal that takes none, raised inside Qt, and nothing connected after it
    ran."""
    states: list[tuple[str, bool]] = []

    def change(dialog: HomeworkDialog) -> int:
        unpin = dialog.findChild(QPushButton, "homeworkUnpin")
        states.append(("opened", unpin.isEnabled()))
        dialog.due.date.setDate(dialog.due.date.date().addDays(-1))
        states.append(("date", unpin.isEnabled()))
        return QDialog.DialogCode.Rejected

    opened_with(monkeypatch, change)
    window._edit_homework("essay")
    assert states == [("opened", True), ("date", False)]

    for step in ("timed", "time"):
        states.clear()

        def other(dialog: HomeworkDialog, step: str = step) -> int:
            unpin = dialog.findChild(QPushButton, "homeworkUnpin")
            if step == "timed":
                dialog.due.timed.setChecked(True)
            else:
                dialog.due.time.setTime(QTime(7, 45))
            states.append((step, unpin.isEnabled()))
            return QDialog.DialogCode.Rejected

        opened_with(monkeypatch, other)
        window._edit_homework("essay")
        assert states == [(step, False)], f"changing the {step} turns it off too"


def test_a_due_field_says_it_changed_with_no_arguments(qapp: QApplication) -> None:  # noqa: F811
    field = DueField("2026-09-24", "probe")
    heard: list[tuple] = []
    field.changed.connect(lambda *args: heard.append(args))
    field.date.setDate(QDate(2026, 9, 25))
    field.timed.setChecked(True)
    field.time.setTime(QTime(8, 15))
    assert heard == [(), (), ()]
