"""What Add and Edit homework start with: a title that is empty and hinted, a due day of tomorrow, a due
time at the end of the school day, and a due date written with its year only when it is not this one."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QDate, QTime
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.widgets import HomeworkDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.sheets.support_homework import SCHOOL, TODAY, essay, go_when, host, opened
from desktop.tests.window_support import free, qapp  # noqa: F401


def test_new_homework_is_due_tomorrow_even_at_22_41(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent)
    assert not dialog.due.isVisibleTo(dialog)
    go_when(dialog)
    assert dialog.due.value() == "2026-09-15"
    free(dialog)
    free(parent)


def test_a_due_given_by_the_caller_is_kept(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = HomeworkDialog(parent, today=TODAY, due="2026-09-18")
    assert dialog.due.value() == "2026-09-18"
    free(dialog)
    free(parent)


def test_the_due_time_starts_at_the_end_of_the_school_day(qapp: QApplication) -> None:  # noqa: F811
    parent = host(SCHOOL)
    dialog = opened(parent)
    go_when(dialog)
    dialog.due.timed.setChecked(True)
    assert dialog.due.time.time() == QTime(14, 30), "08:00 plus 390 minutes"
    free(dialog)
    free(parent)


def test_with_no_school_saved_the_due_time_starts_at_15_00(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent)
    go_when(dialog)
    dialog.due.timed.setChecked(True)
    assert dialog.due.time.time() == QTime(15, 0)
    free(dialog)
    free(parent)


def test_a_saved_due_time_is_not_replaced_by_the_school_day(qapp: QApplication) -> None:  # noqa: F811
    parent = host(SCHOOL)
    dialog = opened(parent, essay(due="2026-09-25T09:15"))
    assert dialog.due.time.time() == QTime(9, 15)
    free(dialog)
    free(parent)


def test_the_year_shows_only_when_it_is_not_this_year(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent)
    go_when(dialog)
    assert dialog.due.date.text() == "Tue 15 Sep"
    dialog.due.date.setDate(QDate(2027, 1, 8))
    assert dialog.due.date.text() == "Fri 8 Jan 2027"
    dialog.due.date.setDate(QDate(2026, 12, 1))
    assert dialog.due.date.text() == "Tue 1 Dec"
    free(dialog)
    free(parent)


@pytest.mark.parametrize("category", ["assignments", "study", None])
def test_new_homework_has_an_empty_title_with_the_example_setup_gives_as_its_hint(
    qapp: QApplication,  # noqa: F811
    category: str | None,
) -> None:
    dialog = HomeworkDialog(None, today="2026-09-24", category=category)
    assert dialog.title.text() == ""
    assert dialog.title.placeholderText() == "e.g. History essay"
    free(dialog)


def test_typing_the_title_gives_exactly_what_was_typed(qapp: QApplication) -> None:  # noqa: F811
    dialog = HomeworkDialog(None, today="2026-09-24", category="assignments")
    dialog.show()
    dialog.title.setFocus()
    QTest.keyClicks(dialog.title, "Math worksheet")
    dialog.accept()
    assert dialog.result() == dialog.DialogCode.Accepted
    assert dialog.assignment()["title"] == "Math worksheet"
    free(dialog)


def test_saving_with_no_title_asks_for_one_in_words(qapp: QApplication) -> None:  # noqa: F811
    dialog = HomeworkDialog(None, today="2026-09-24", category="assignments")
    dialog.show()
    qapp.processEvents()
    dialog.accept()
    assert dialog.result() != dialog.DialogCode.Accepted
    assert dialog.title_problem.text() == "Give the homework a title."
    assert dialog.title_problem.isVisible()
    free(dialog)


def test_editing_homework_keeps_its_title(qapp: QApplication) -> None:  # noqa: F811
    dialog = HomeworkDialog(None, essay(), "2026-09-24")
    assert dialog.title.text() == "History essay"
    free(dialog)


def test_add_homework_from_the_window_opens_with_the_hint_not_the_word(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[str, str]] = []

    def run(dialog: HomeworkDialog) -> int:
        seen.append((dialog.title.text(), dialog.title.placeholderText()))
        return 0

    monkeypatch.setattr(HomeworkDialog, "exec", run)
    window._add_homework()
    assert seen == [("", "e.g. History essay")]
