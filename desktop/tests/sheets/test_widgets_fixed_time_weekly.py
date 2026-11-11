"""The plain look's Add fixed time and Edit fixed time sheet: the "Repeats every week" switch and its optional
Until date, the refusal under the Until field, what the window saves, and the delete question for a weekly
fixed time. Where the rows sit and how wide they are, is a look: pictures/_sheets_g13.py.

Dates (the one clock's week is Monday 2 November 2026, Thursday 19:00): Saturday 7 Nov is this week's
Saturday, Sat 14 Nov the next. Until Fri 13 Nov ends the repeat before Sat 14 Nov."""

# ruff: noqa: F811
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QWidget

from desktop.native import widgets
from desktop.native.widgets import BlockDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.sheets.support_dialogs import school
from desktop.tests.sheets.support_soccer import soccer
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import host, qapp, settled  # noqa: F401

SATURDAY = 5
NEXT_WEEK = "2026-11-09"


def go_to(qapp: QApplication, window: NativeWindow, week: str) -> None:
    window.session.load_week(week)
    wait_until(qapp, lambda: window.session.week_start == week and not window.session.busy)
    settled(qapp, window)


def piano(window: NativeWindow) -> dict | None:
    return next((item for item in window.session.blocks if item["title"] == "Piano"), None)


def saturday_dialog(window: NativeWindow, block: dict | None = None, **fields: object) -> BlockDialog:
    dialog = BlockDialog(window, block, day=SATURDAY, start="10:00", **fields)
    dialog.title.setText("Piano")
    dialog.show()
    return dialog


def run_and_commit(window: NativeWindow, dialog: BlockDialog, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dialog, "exec", lambda: dialog.accept() or dialog.result(), raising=False)
    window._commit_block(dialog)


def go_to_when(dialog: BlockDialog) -> None:
    dialog.title.setText("Piano")
    dialog._add_primary()


def test_the_when_step_has_the_switch_and_until_appears_only_once_it_is_on(
    qapp: QApplication, window: NativeWindow  # noqa: F811
) -> None:
    dialog = saturday_dialog(window)
    go_to_when(dialog)
    assert dialog.repeat.text() == "Repeats every week"
    assert dialog.repeat.isChecked() is False
    assert not dialog.repeat.isHidden()
    assert dialog._until_field.isHidden()
    assert dialog.weekly() is False and dialog.until_value() == ""
    dialog.repeat.setChecked(True)
    assert not dialog._until_field.isHidden()
    assert dialog.until_on.isChecked() is False and dialog.until.isEnabled() is False
    assert dialog.until_value() == ""
    dialog.until_on.setChecked(True)
    assert dialog.until.isEnabled() is True
    assert dialog.until_value() != ""


def test_the_switch_is_on_the_when_step_only(qapp: QApplication, window: NativeWindow) -> None:  # noqa: F811
    dialog = saturday_dialog(window)
    assert dialog.repeat.isHidden()
    go_to_when(dialog)
    assert not dialog.repeat.isHidden()
    dialog._add_primary()
    assert dialog.repeat.isHidden()


def test_a_weekly_fixed_time_with_until_is_saved_and_cut_after_that_day(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    dialog = saturday_dialog(window)
    dialog._add_step = 2
    dialog._apply_add_step()
    dialog.repeat.setChecked(True)
    dialog.until_on.setChecked(True)
    dialog.until.setDate(QDate(2026, 11, 14))
    run_and_commit(window, dialog, monkeypatch)
    settled(qapp, window)
    made = piano(window)
    assert made is not None and made["id"].startswith("weekly-") and made["until"] == "2026-11-14"
    go_to(qapp, window, NEXT_WEEK)
    assert piano(window) is not None
    go_to(qapp, window, "2026-11-16")
    assert piano(window) is None


def test_an_until_before_the_first_day_is_refused_under_the_field_and_nothing_is_saved(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    dialog = saturday_dialog(window)
    dialog._add_step = 2
    dialog._apply_add_step()
    dialog.repeat.setChecked(True)
    dialog.until_on.setChecked(True)
    dialog.until.setDate(QDate(2026, 11, 6))
    dialog.accept()
    assert dialog.result() != dialog.DialogCode.Accepted
    assert dialog.until_problem.text() == "Until can't be before the first day, Sat 7 Nov."
    assert dialog._add_step == 1
    assert not dialog.until_problem.isHidden()
    assert piano(window) is None
    dialog.until.setDate(QDate(2026, 11, 7))
    assert dialog.until_problem.text() == ""
    dialog.accept()
    assert dialog.result() == dialog.DialogCode.Accepted


def test_with_the_switch_off_the_fixed_time_stays_in_the_open_week(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    dialog = saturday_dialog(window)
    dialog._add_step = 2
    dialog._apply_add_step()
    run_and_commit(window, dialog, monkeypatch)
    settled(qapp, window)
    made = piano(window)
    assert made is not None and not made["id"].startswith("weekly-") and "until" not in made
    go_to(qapp, window, NEXT_WEEK)
    assert piano(window) is None


def test_an_until_inside_the_open_week_removes_its_later_days_when_added(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    go_to(qapp, window, NEXT_WEEK)
    dialog = saturday_dialog(window)
    for index, check in enumerate(dialog.days):
        check.setChecked(index in (1, 3))
    dialog._add_step = 2
    dialog._apply_add_step()
    dialog.repeat.setChecked(True)
    dialog.until_on.setChecked(True)
    dialog.until.setDate(QDate(2026, 11, 10))
    run_and_commit(window, dialog, monkeypatch)
    settled(qapp, window)
    go_to(qapp, window, "2026-11-16")
    go_to(qapp, window, NEXT_WEEK)
    assert sorted(piano(window)["days"]) == [1]


def test_changing_until_to_a_day_inside_the_open_week_removes_its_later_days_when_edited(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    window.session.add_block(dict(soccer(), title="Piano", days=[1, 3]), weekly=True, until="")
    window.session.save()
    settled(qapp, window)
    go_to(qapp, window, NEXT_WEEK)
    assert sorted(piano(window)["days"]) == [1, 3]
    dialog = BlockDialog(window, piano(window))
    dialog.show()
    dialog.until_on.setChecked(True)
    dialog.until.setDate(QDate(2026, 11, 10))
    run_and_commit(window, dialog, monkeypatch)
    settled(qapp, window)
    go_to(qapp, window, "2026-11-16")
    go_to(qapp, window, NEXT_WEEK)
    assert sorted(piano(window)["days"]) == [1]


def test_editing_a_weekly_fixed_time_shows_the_switch_on_with_its_until(
    qapp: QApplication, window: NativeWindow  # noqa: F811
) -> None:
    block = {**soccer(), "id": "weekly-soccer", "until": "2026-11-14"}
    dialog = BlockDialog(window, block)
    dialog.show()
    assert dialog.repeat.isChecked() is True and not dialog.repeat.isHidden()
    assert dialog.until_on.isChecked() is True
    assert dialog.until.date() == QDate(2026, 11, 14)
    assert dialog.weekly() is True and dialog.until_value() == "2026-11-14"


def test_school_from_setup_has_no_switch_because_setup_owns_its_repeat(
    qapp: QApplication, window: NativeWindow  # noqa: F811
) -> None:
    dialog = BlockDialog(window, school())
    dialog.show()
    assert dialog.repeat.isHidden() and dialog.weekly() is None


def test_this_day_only_hides_the_switch_because_it_would_repeat_just_that_day(
    qapp: QApplication, window: NativeWindow  # noqa: F811
) -> None:
    dialog = BlockDialog(window, soccer(), occurrence_day=1)
    dialog.show()
    assert dialog.scope() == "occurrence"
    assert dialog.repeat.isHidden() and dialog.weekly() is None
    dialog.scope_series.setChecked(True)
    assert not dialog.repeat.isHidden() and dialog.weekly() is False


def test_the_switch_off_in_edit_keeps_this_week_and_ends_the_repeat_from_next_week(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    window.session.add_block(dict(soccer(), title="Piano", days=[SATURDAY]), weekly=True, until="")
    window.session.save()
    settled(qapp, window)
    dialog = BlockDialog(window, piano(window))
    dialog.show()
    dialog.repeat.setChecked(False)
    run_and_commit(window, dialog, monkeypatch)
    settled(qapp, window)
    assert piano(window) is not None and not piano(window)["id"].startswith("weekly-")
    go_to(qapp, window, NEXT_WEEK)
    assert piano(window) is None


def test_deleting_a_weekly_fixed_time_asks_this_week_only_or_this_week_and_later(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch, host: QWidget  # noqa: F811
) -> None:
    asked: list[tuple] = []

    class Answer:
        def __init__(self, parent, title, question, answers, **kwargs) -> None:
            asked.append((title, [label for _key, label, _kind in answers], kwargs.get("note")))
            self.answer = "stay"

        def exec(self) -> int:
            return 0

    monkeypatch.setattr(widgets, "ConfirmSheet", Answer)
    block = {**soccer(), "id": "weekly-soccer", "days": [SATURDAY]}
    # Opened from its one day, as a double-click on the week does: "this day only" is the whole block.
    dialog = BlockDialog(host, block, occurrence_day=SATURDAY)
    dialog.show()
    dialog.delete_button.click()
    assert asked == [
        (
            "Delete Soccer practice?",
            ["Cancel", "This week only", "This week and later"],
            "This week and later can't be undone.",
        )
    ]
    assert dialog.deleted() is False
