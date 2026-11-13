# ruff: noqa: F811
"""The sheets and dialogs of a week that starts on Wednesday name each day from its date. The clock is
Thursday 5 November 2026, so the open week runs Wednesday 4 to Tuesday 10 November and a block's day 0
is Wednesday, day 5 Monday 9. A day named from its place in a Monday week is the bug these catch."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton

from desktop.native import fields
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import free, qapp, settled  # noqa: F401

CLUB = {"id": "club", "title": "Club", "kind": "locked", "start": "16:00", "duration_min": 60, "days": [0, 5]}
SHOWN = ["Wed", "Thu", "Fri", "Sat", "Sun", "Mon", "Tue"]


def _wednesday_week(qapp: QApplication, window: NativeWindow) -> None:
    fields.save_week_starts_on("wednesday")
    wait_until(qapp, lambda: window.session.week_start == "2026-11-04" and not window.session.busy)
    window.session.add_block(dict(CLUB))
    window.session.save()
    settled(qapp, window)


def test_the_widgets_block_editor_names_its_days_from_the_week(
    qapp: QApplication, window: NativeWindow
) -> None:
    from desktop.native.widgets import BlockDialog

    _wednesday_week(qapp, window)
    whole = BlockDialog(window, dict(CLUB))
    one_day = BlockDialog(window, dict(CLUB), occurrence_day=5)
    try:
        pills = [button for button in whole.findChildren(QPushButton) if button.property("pill")]
        assert [pill.text() for pill in pills] == SHOWN
        assert [pill.isChecked() for pill in pills] == [day in (0, 5) for day in range(7)]
        pills[1].click()
        whole.accept()
        assert whole.block()["days"] == [0, 1, 5]
        assert one_day.missed.text() == "I missed it on Monday"
        assert one_day.scope_series.text() == "Every Wed and Mon"
    finally:
        free(whole)
        free(one_day)


def test_the_material_block_sheet_names_its_days_from_the_week(
    qapp: QApplication, window: NativeWindow
) -> None:
    from desktop.native.material.sheet_block import BlockDraft

    _wednesday_week(qapp, window)
    draft = BlockDraft(window.session, dict(CLUB), occurrence_day=5)
    form = draft.form()
    days = [(day["label"], day["date"]) for day in form["days"]]
    assert days == list(zip(SHOWN, range(4, 11), strict=True))
    assert form["missedLabel"] == "I missed it on Monday"
    draft.scope = "occurrence"
    assert draft.delete_question()["body"].startswith("Delete Club on Monday 9 Nov only?")


def test_the_homework_when_days_and_choose_a_time_start_on_the_weeks_first_day(
    qapp: QApplication, window: NativeWindow
) -> None:
    from desktop.native.widgets import ChooseTimeDialog, HomeworkDialog

    _wednesday_week(qapp, window)
    homework = HomeworkDialog(window, today="2026-11-05")
    homework._dress_when_days()
    choose = ChooseTimeDialog(
        window,
        {"id": "essay", "title": "Essay", "kind": "flexible", "duration_min": 45, "days": list(range(7))},
        window.session.week_start,
        list(range(7)),
        window.session.blocks,
        None,
        1,
        19 * 60,
        ("2026-11-05", 19 * 60),
    )
    try:
        for picker in (homework.when_day, choose.day):
            words = [button.text() for button in picker.buttons]
            assert words[0] == "Wed\n4" and words[5] == "Mon\n9", words
            assert picker.buttons[0].accessibleName() == "Wednesday"
        # Wednesday 4 is over by Thursday evening; Thursday 5, today, is not.
        assert not homework.when_day.buttons[0].isEnabled()
        assert homework.when_day.buttons[1].isEnabled()
    finally:
        free(homework)
        free(choose)


def test_a_day_deleted_from_the_week_is_said_by_its_own_name(
    qapp: QApplication, window: NativeWindow
) -> None:
    _wednesday_week(qapp, window)
    window._delete_block(dict(CLUB), "occurrence", 5, every_week=False)
    settled(qapp, window)
    assert window.toast.text() == "Deleted Club on Monday from this week."


def test_a_new_school_block_is_on_monday_to_friday_of_the_week(
    qapp: QApplication, window: NativeWindow
) -> None:
    from desktop.native.material.sheet_block import BlockDraft
    from desktop.native.widgets import BlockDialog

    _wednesday_week(qapp, window)
    # Wednesday 4 to Friday 6 are days 0 to 2, Monday 9 and Tuesday 10 days 5 and 6.
    school_days = [0, 1, 2, 5, 6]
    dialog = BlockDialog(window, category="class")
    try:
        pills = [button for button in dialog.findChildren(QPushButton) if button.property("pill")]
        assert [pill.text() for pill in pills if pill.isChecked()] == ["Wed", "Thu", "Fri", "Mon", "Tue"]
        assert dialog.day_picker.days() == school_days
    finally:
        free(dialog)
    assert BlockDraft(window.session, None, category="class").days == school_days

