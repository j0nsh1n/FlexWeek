# ruff: noqa: F811
"""The Material Add fixed time and Edit fixed time sheet's "Repeats every week" switch and optional Until
date: what the switch saves, where Until cuts, the refusal under the Until field, editing a weekly fixed
time, and the delete question for one.

Dates (the one clock's week is Monday 2 November 2026, Thursday 19:00): Saturday 7 Nov is this week's
Saturday, Sat 14 Nov the next. Until Fri 13 Nov ends the repeat before Sat 14 Nov; Until Sat 14 Nov keeps it.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.sheets.support_material_sheet_fixtures import (  # noqa: E402,F401
    open_light,
    qapp,
    settle,
    sheets,
    shell,
)
from desktop.tests.waiting import wait_until  # noqa: E402

SATURDAY = 5
NEXT_WEEK = "2026-11-09"
WEEK_AFTER = "2026-11-16"


PIANO_TUE_THU = {
    "id": "piano", "title": "Piano", "kind": "locked", "category": "extra", "start": "16:00",
    "duration_min": 60, "days": [1, 3],
}


def go_to(qapp: QApplication, shell: NativeWindow, week: str) -> None:
    shell.session.load_week(week)
    wait_until(qapp, lambda: shell.session.week_start == week and not shell.session.busy)
    settle(qapp, shell)


def saturday_piano(sheets, *, repeats: bool, until: str = "") -> None:
    """Add fixed time for Saturday 10:00 to 11:00, named Piano, through the sheet's three steps."""
    sheets.openBlockAt(SATURDAY, 10 * 60, 11 * 60)
    sheets.setText("title", "Piano")
    sheets.next()
    if repeats:
        sheets.setFlag("repeats", True)
    if until:
        sheets.setText("until", until)
    sheets.next()
    sheets.next()


def piano(shell: NativeWindow) -> dict | None:
    return next((item for item in shell.session.blocks if item["title"] == "Piano"), None)


def test_the_when_step_offers_the_switch_and_an_optional_until_that_starts_empty(sheets) -> None:
    sheets.openBlockAt(SATURDAY, 10 * 60, 11 * 60)
    sheets.setText("title", "Piano")
    sheets.next()
    form = sheets.form
    assert form["repeatShown"] is True
    assert form["repeatLabel"] == "Repeats every week"
    assert form["repeats"] is False
    assert form["untilShown"] is False
    sheets.setFlag("repeats", True)
    form = sheets.form
    assert form["untilShown"] is True
    assert form["untilLabel"] == "Until"
    assert form["until"] == ""
    assert form["untilOptions"][0] == {"value": "", "label": "No end"}


def test_a_weekly_fixed_time_with_until_saturday_shows_next_saturday_and_not_the_one_after(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    saturday_piano(sheets, repeats=True, until="2026-11-14")
    assert sheets.kind == ""
    made = piano(shell)
    assert made is not None and made["id"].startswith("weekly-") and made["until"] == "2026-11-14"
    settle(qapp, shell)
    go_to(qapp, shell, NEXT_WEEK)
    assert piano(shell) is not None
    go_to(qapp, shell, WEEK_AFTER)
    assert piano(shell) is None


def test_until_on_the_friday_before_ends_it_before_next_saturday(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    saturday_piano(sheets, repeats=True, until="2026-11-13")
    settle(qapp, shell)
    go_to(qapp, shell, NEXT_WEEK)
    assert piano(shell) is None


def piano_days(shell: NativeWindow) -> list[int] | None:
    found = piano(shell)
    return sorted(found["days"]) if found else None


def reload_week(qapp: QApplication, shell: NativeWindow) -> None:
    week = shell.session.week_start
    go_to(qapp, shell, WEEK_AFTER)
    go_to(qapp, shell, week)


def test_an_until_inside_the_open_week_removes_its_later_days_when_added(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    go_to(qapp, shell, NEXT_WEEK)
    sheets.openBlockAt(1, 16 * 60, 17 * 60)
    sheets.setText("title", "Piano")
    sheets.next()
    sheets.toggleDay(3)
    sheets.setFlag("repeats", True)
    sheets.setText("until", "2026-11-10")
    sheets.next()
    sheets.next()
    settle(qapp, shell)
    reload_week(qapp, shell)
    assert piano_days(shell) == [1]


def test_changing_until_to_a_day_inside_the_open_week_removes_its_later_days_when_edited(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    shell.session.add_block({**PIANO_TUE_THU}, weekly=True, until="")
    shell.session.save()
    settle(qapp, shell)
    go_to(qapp, shell, NEXT_WEEK)
    assert piano_days(shell) == [1, 3]
    sheets.editBlock(piano(shell)["id"], 1)
    sheets.setText("scope", "series")
    sheets.setText("until", "2026-11-10")
    sheets.save()
    settle(qapp, shell)
    reload_week(qapp, shell)
    assert piano_days(shell) == [1]


def test_with_the_switch_off_the_fixed_time_is_only_in_the_open_week(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    saturday_piano(sheets, repeats=False)
    made = piano(shell)
    assert made is not None and not made["id"].startswith("weekly-") and "until" not in made
    settle(qapp, shell)
    go_to(qapp, shell, NEXT_WEEK)
    assert piano(shell) is None


def test_an_until_before_the_first_day_is_refused_under_the_field_and_nothing_is_saved(
    shell: NativeWindow, sheets
) -> None:
    sheets.openBlockAt(SATURDAY, 10 * 60, 11 * 60)
    sheets.setText("title", "Piano")
    sheets.next()
    sheets.setFlag("repeats", True)
    sheets.setText("until", "2026-11-06")
    sheets.next()
    assert sheets.form["step"] == 1
    assert sheets.form["untilProblem"] == "Until can't be before the first day, Sat 7 Nov."
    assert sheets.kind == "block"
    assert piano(shell) is None
    sheets.setText("until", "2026-11-07")
    assert sheets.form["untilProblem"] == ""
    sheets.next()
    sheets.next()
    assert piano(shell) is not None


def test_editing_a_weekly_fixed_time_shows_the_switch_on_and_its_until(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    saturday_piano(sheets, repeats=True, until="2026-11-14")
    settle(qapp, shell)
    sheets.editBlock(piano(shell)["id"], SATURDAY)
    form = sheets.form
    assert form["heading"] == "Edit fixed time"
    assert form["repeatShown"] is True and form["repeats"] is True
    assert form["until"] == "2026-11-14"
    assert any(option["value"] == "2026-11-14" for option in form["untilOptions"])


def test_turning_the_switch_off_in_edit_keeps_this_week_and_ends_it_from_next_week(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    saturday_piano(sheets, repeats=True)
    settle(qapp, shell)
    sheets.editBlock(piano(shell)["id"], SATURDAY)
    sheets.setFlag("repeats", False)
    sheets.save()
    assert piano(shell) is not None and not piano(shell)["id"].startswith("weekly-")
    settle(qapp, shell)
    go_to(qapp, shell, NEXT_WEEK)
    assert piano(shell) is None


def test_the_switch_on_in_edit_makes_an_ordinary_fixed_time_weekly_from_this_week(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    saturday_piano(sheets, repeats=False)
    settle(qapp, shell)
    sheets.editBlock(piano(shell)["id"], SATURDAY)
    assert sheets.form["repeats"] is False
    sheets.setFlag("repeats", True)
    sheets.save()
    settle(qapp, shell)
    assert piano(shell)["id"].startswith("weekly-")
    go_to(qapp, shell, NEXT_WEEK)
    assert piano(shell) is not None


def test_deleting_a_weekly_fixed_time_asks_this_week_only_or_this_week_and_later(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    saturday_piano(sheets, repeats=True)
    settle(qapp, shell)
    sheets.editBlock(piano(shell)["id"], SATURDAY)
    sheets.remove()
    labels = [answer["label"] for answer in sheets.ask["answers"]]
    assert labels == ["Cancel", "This week only", "This week and later"]
    assert "can't be undone" in sheets.ask["body"]
    sheets.answer("week")
    settle(qapp, shell)
    assert piano(shell)["missed_days"] == [SATURDAY]
    go_to(qapp, shell, NEXT_WEEK)
    assert piano(shell) is not None


def test_deleting_one_day_of_a_two_day_weekly_fixed_time_also_offers_this_day_only(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    sheets.openBlockAt(SATURDAY, 10 * 60, 11 * 60)
    sheets.setText("title", "Piano")
    sheets.next()
    sheets.toggleDay(6)
    sheets.setFlag("repeats", True)
    sheets.next()
    sheets.next()
    settle(qapp, shell)
    sheets.editBlock(piano(shell)["id"], SATURDAY)
    sheets.remove()
    labels = [answer["label"] for answer in sheets.ask["answers"]]
    assert labels == ["Cancel", "This day only", "This week only", "This week and later"]


def test_this_day_only_hides_the_switch_because_it_would_repeat_just_that_day(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    sheets.openBlockAt(SATURDAY, 10 * 60, 11 * 60)
    sheets.setText("title", "Piano")
    sheets.next()
    sheets.toggleDay(6)
    sheets.next()
    sheets.next()
    settle(qapp, shell)
    sheets.editBlock(piano(shell)["id"], SATURDAY)
    assert sheets.form["scope"] == "occurrence"
    assert sheets.form["repeatShown"] is False
    sheets.setText("scope", "series")
    assert sheets.form["repeatShown"] is True


def test_school_from_setup_has_no_switch_because_setup_owns_its_repeat(sheets) -> None:
    sheets.editBlock("school", 0)
    assert sheets.form["repeatShown"] is False
    sheets.setText("scope", "series")
    assert sheets.form["scope"] == "series"
    assert sheets.form["repeatShown"] is False


def test_the_switch_is_not_on_flexible_work(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    work = next(item for item in shell.session.blocks if item.get("assignment_id") == "essay")
    sheets.editBlock(work["id"], 3)
    assert sheets.kind == "homework"
    assert "repeatShown" not in sheets.form


def weekly_saturday_piano(qapp: QApplication, shell: NativeWindow, sheets) -> str:
    saturday_piano(sheets, repeats=True)
    settle(qapp, shell)
    return piano(shell)["id"]


def piano_title_in(qapp: QApplication, shell: NativeWindow, week: str) -> str:
    go_to(qapp, shell, week)
    return next(item for item in shell.session.blocks if item["id"].startswith("weekly-"))["title"]


def test_saving_a_changed_weekly_fixed_time_asks_this_week_only_or_this_week_and_later(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    block_id = weekly_saturday_piano(qapp, shell, sheets)
    sheets.editBlock(block_id, SATURDAY)
    sheets.setText("title", "Piano lesson")
    sheets.save()
    ask = sheets.ask
    assert ask["id"] == "edit-block"
    assert ask["title"] == "Change Piano?"
    labels = [answer["label"] for answer in ask["answers"]]
    assert labels == ["Cancel", "This week only", "This week and later"]
    assert sheets.kind == "block", "the sheet stays open under the question"
    assert piano(shell)["title"] == "Piano", "nothing is saved before the answer"


def test_cancelling_the_which_weeks_question_returns_to_the_sheet_with_the_typing_intact(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    block_id = weekly_saturday_piano(qapp, shell, sheets)
    sheets.editBlock(block_id, SATURDAY)
    sheets.setText("title", "Piano lesson")
    sheets.save()
    sheets.answer("stay")
    assert sheets.ask == {} and sheets.kind == "block"
    assert sheets.form["title"] == "Piano lesson"
    assert piano(shell)["title"] == "Piano"
    # Esc on the question does the same.
    sheets.save()
    assert sheets.ask["id"] == "edit-block"
    sheets.closeSheet()
    assert sheets.ask == {} and sheets.kind == "block"
    assert sheets.form["title"] == "Piano lesson"
    assert piano(shell)["title"] == "Piano"


def test_this_week_only_changes_this_week_and_leaves_later_weeks(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    block_id = weekly_saturday_piano(qapp, shell, sheets)
    sheets.editBlock(block_id, SATURDAY)
    sheets.setText("title", "Piano lesson")
    sheets.save()
    sheets.answer("week")
    settle(qapp, shell)
    assert sheets.kind == "" and piano_title_in(qapp, shell, NEXT_WEEK) == "Piano"
    go_to(qapp, shell, "2026-11-02")
    assert any(item["title"] == "Piano lesson" for item in shell.session.blocks)


def test_this_week_and_later_changes_every_later_week_too(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    block_id = weekly_saturday_piano(qapp, shell, sheets)
    go_to(qapp, shell, WEEK_AFTER)
    go_to(qapp, shell, "2026-11-02")
    sheets.editBlock(block_id, SATURDAY)
    sheets.setText("title", "Piano lesson")
    sheets.save()
    sheets.answer("every")
    settle(qapp, shell)
    assert piano_title_in(qapp, shell, NEXT_WEEK) == "Piano lesson"
    assert piano_title_in(qapp, shell, WEEK_AFTER) == "Piano lesson"


def test_nothing_changed_or_only_the_repeat_changed_asks_nothing(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    block_id = weekly_saturday_piano(qapp, shell, sheets)
    sheets.editBlock(block_id, SATURDAY)
    sheets.save()
    assert sheets.ask == {} and sheets.kind == ""
    settle(qapp, shell)
    sheets.editBlock(block_id, SATURDAY)
    sheets.setText("until", "2026-11-14")
    sheets.save()
    assert sheets.ask == {} and sheets.kind == ""
    settle(qapp, shell)
    assert piano(shell)["until"] == "2026-11-14"
    sheets.editBlock(piano(shell)["id"], SATURDAY)
    sheets.setFlag("repeats", False)
    sheets.save()
    assert sheets.ask == {} and sheets.kind == ""


def test_one_day_of_a_two_day_weekly_fixed_time_asks_only_after_every_day_is_chosen(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    sheets.openBlockAt(SATURDAY, 10 * 60, 11 * 60)
    sheets.setText("title", "Piano")
    sheets.next()
    sheets.toggleDay(6)
    sheets.setFlag("repeats", True)
    sheets.next()
    sheets.next()
    settle(qapp, shell)
    sheets.editBlock(piano(shell)["id"], SATURDAY)
    assert sheets.form["scope"] == "occurrence"
    sheets.setText("title", "Piano lesson")
    sheets.save()
    assert sheets.ask == {} and sheets.kind == "", "this day only is this day of this week"
    settle(qapp, shell)
    sheets.editBlock(next(i for i in shell.session.blocks if i["title"] == "Piano")["id"], SATURDAY)
    sheets.setText("scope", "series")
    sheets.setText("title", "Piano class")
    sheets.save()
    assert sheets.ask["id"] == "edit-block"


def test_a_new_repeat_that_doubles_a_hand_made_copy_in_a_later_week_gets_an_alert_until_ok(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    go_to(qapp, shell, NEXT_WEEK)
    saturday_piano(sheets, repeats=False)
    settle(qapp, shell)
    go_to(qapp, shell, "2026-11-02")
    saturday_piano(sheets, repeats=True)
    wait_until(qapp, lambda: sheets.ask.get("id") == "twin-weeks", what="the alert")
    ask = sheets.ask
    assert ask["title"] == "Piano is already in later weeks"
    assert ask["body"] == (
        "Piano also sits on its own in the week of 9 Nov, so it shows twice there. "
        "Delete the extra one in that week if you don't want both."
    )
    assert [answer["label"] for answer in ask["answers"]] == ["OK"]
    for _ in range(3):
        qapp.processEvents()
    assert sheets.ask["id"] == "twin-weeks", "it does not close by itself"
    sheets.answer("ok")
    assert sheets.ask == {}
    go_to(qapp, shell, NEXT_WEEK)
    assert sum(1 for item in shell.session.blocks if item["title"] == "Piano") == 2, "nothing was removed"


def test_the_twin_alert_stays_up_when_a_sheet_is_opened_over_it_and_waits_behind_a_question(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    sheets._on_twins("Piano", ["2026-11-09"])
    assert sheets.ask["id"] == "twin-weeks"
    sheets.openBlockAt(SATURDAY, 10 * 60, 11 * 60)
    assert sheets.ask["id"] == "twin-weeks", "opening a sheet is not an answer"
    sheets.answer("ok")
    assert sheets.ask == {}
    sheets.setText("title", "Piano")
    sheets.closeSheet()
    assert sheets.ask["id"] == "discard"
    sheets._on_twins("Piano", ["2026-11-09"])
    assert sheets.ask["id"] == "discard", "a question is never replaced"
    sheets.answer("stay")
    assert sheets.ask["id"] == "twin-weeks", "it comes after the question is answered"
