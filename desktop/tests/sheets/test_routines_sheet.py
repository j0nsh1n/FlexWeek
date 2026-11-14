# ruff: noqa: F811
"""The Material Routines sheet: it applies a saved routine to the open week through the session and
refuses an apply with no routine or no weekday chosen.

Expected words and values come from the Widgets sheet's wording.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtGui import QAccessible  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.material_support import pump  # noqa: E402
from desktop.tests.sheets.support_material_sheet_fixtures import (  # noqa: E402,F401
    find_named,
    open_light,
    qapp,
    settle,
    sheets,
    shell,
)
from desktop.tests.waiting import wait_until  # noqa: E402


def test_routines_apply_to_the_open_week_through_the_session(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    shell.session.routines["r-1"] = {
        "id": "r-1",
        "name": "Weekend",
        "revision": 1,
        "blocks": [
            {
                "template_id": "t1",
                "title": "Long walk",
                "days": [5],
                "start": "10:00",
                "duration_min": 60,
                "category": "exercise",
            }
        ],
    }
    sheets.openRoutines()
    pump(qapp)
    assert sheets.form["intro"] == "Pick a routine, the week to copy it into and the days to copy."
    assert sheets.form["rows"][0]["name"] == "Weekend"
    assert sheets.form["rows"][0]["detail"] == "1 fixed times"
    assert find_named(shell._material_page.root, "routinesApply").property("text") == "Apply"
    sheets.applyRoutine()
    assert sheets.form["error"] == "Choose a saved routine."
    sheets.selectRoutine("r-1")
    assert [day["on"] for day in sheets.form["days"]] == [False] * 5 + [True, False]
    sheets.toggleRoutineDay(5)
    sheets.applyRoutine()
    assert sheets.form["error"] == "Choose at least one weekday to copy."
    sheets.toggleRoutineDay(5)
    sheets.applyRoutine()
    wait_until(qapp, lambda: sheets.kind == "")
    assert any(item["title"] == "Long walk" for item in shell.session.blocks)
    assert sheets.notice == "Added the Weekend routine."
    settle(qapp, shell)


def test_a_routine_picked_in_a_week_from_wednesday_ticks_its_own_weekdays(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    from desktop.native import fields

    # The clock is Thursday 5 November 2026: from Wednesday the week runs Wednesday 4 to Tuesday 10,
    # so Saturday 7 is day 3 and Monday 9 day 5.
    fields.save_week_starts_on("wednesday")
    wait_until(qapp, lambda: shell.session.week_start == "2026-11-04" and not shell.session.busy)
    settle(qapp, shell)
    shell.session.routines["r-2"] = {
        "id": "r-2",
        "name": "Saturday and Monday",
        "revision": 1,
        "blocks": [
            {
                "template_id": "t1",
                "title": "Long walk",
                "days": [0, 5],
                "start": "10:00",
                "duration_min": 60,
                "category": "exercise",
            }
        ],
    }
    sheets.openRoutines()
    pump(qapp)
    sheets.selectRoutine("r-2")
    ticked = [day["label"] for day in sheets.form["days"] if day["on"]]
    assert ticked == ["Sat", "Mon"]
    assert [day["value"] for day in sheets.form["days"] if day["on"]] == [3, 5]


def test_days_ticked_in_the_routines_sheet_keep_their_weekdays_when_the_week_start_changes(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    from desktop.native import fields

    # The clock is Thursday 5 November 2026. From Monday the week runs Monday 2 to Sunday 8; from
    # Wednesday it runs Wednesday 4 to Tuesday 10. Wednesday 4 stays where it is (day 0); Monday 2 is
    # not in the new week, so Monday is Monday 9 (day 5).
    routine = {
        "id": "r-3",
        "name": "Monday and Wednesday",
        "revision": 1,
        "blocks": [
            {
                "template_id": "t1",
                "title": "Long walk",
                "days": [0, 2],
                "start": "10:00",
                "duration_min": 60,
                "category": "exercise",
            }
        ],
    }
    shell.session.routines["r-3"] = routine
    sheets.openRoutines()
    pump(qapp)
    sheets.selectRoutine("r-3")
    ticked = [(day["label"], day["date"]) for day in sheets.form["days"] if day["on"]]
    assert ticked == [("Mon", 2), ("Wed", 4)]
    fields.save_week_starts_on("wednesday")
    wait_until(qapp, lambda: shell.session.week_start == "2026-11-04" and not shell.session.busy)
    settle(qapp, shell)
    # The new week's read fetched the routines again, and this one was never saved to the server.
    shell.session.routines["r-3"] = routine
    pump(qapp)
    assert sheets.kind == "routines"
    ticked = [(day["value"], day["label"], day["date"]) for day in sheets.form["days"] if day["on"]]
    assert ticked == [(0, "Wed", 4), (5, "Mon", 9)]
    sheets.applyRoutine()
    wait_until(qapp, lambda: sheets.kind == "", what=lambda: str(sheets.form.get("error")))
    walk = [item for item in shell.session.blocks if item["title"] == "Long walk"]
    assert sorted(day for item in walk for day in item["days"]) == [0, 5]
    settle(qapp, shell)


def _chip_name(shell: NativeWindow, name: str) -> str:
    face = QAccessible.queryAccessibleInterface(find_named(shell._material_page.root, name))
    assert face is not None, name
    return face.text(QAccessible.Text.Name)


def test_moved_routine_days_are_marked_named_and_announced(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    from desktop.native import fields

    # Monday-start week Mon 2 to Sun 8: Monday 2 and Wednesday 4 ticked. From Wednesday the
    # week is Wed 4 to Tue 10, so Wednesday stays and Monday 2 becomes Monday 9.
    shell.session.routines["r-4"] = {
        "id": "r-4",
        "name": "Monday and Wednesday",
        "revision": 1,
        "blocks": [
            {
                "template_id": "t1",
                "title": "Long walk",
                "days": [0, 2],
                "start": "10:00",
                "duration_min": 60,
                "category": "exercise",
            }
        ],
    }
    sheets.openRoutines()
    pump(qapp)
    sheets.selectRoutine("r-4")
    assert [day["value"] for day in sheets.form["days"] if day["on"]] == [0, 2]
    fields.save_week_starts_on("wednesday")
    wait_until(qapp, lambda: shell.session.week_start == "2026-11-04" and not shell.session.busy)
    settle(qapp, shell)
    pump(qapp)
    form = sheets.form
    assert form["movedNote"] == "Monday 2 isn't in this week any more, so it moved to Monday 9."
    by_value = {day["value"]: day for day in form["days"]}
    assert by_value[0]["on"] and not by_value[0].get("moved")
    assert by_value[5]["on"] and by_value[5]["moved"]
    assert by_value[5]["movedFrom"] == "Monday 2"
    assert _chip_name(shell, "routineDay5") == "Mon 9, moved from Monday 2"
    assert _chip_name(shell, "routineDay0") == "Wed 4"
    assert _chip_name(shell, "routinesMovedNote") == form["movedNote"]


def test_touching_the_routines_row_clears_the_moved_mark(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    from desktop.native import fields

    shell.session.routines["r-5"] = {
        "id": "r-5",
        "name": "Monday",
        "revision": 1,
        "blocks": [
            {
                "template_id": "t1",
                "title": "Long walk",
                "days": [0],
                "start": "10:00",
                "duration_min": 60,
                "category": "exercise",
            }
        ],
    }
    sheets.openRoutines()
    pump(qapp)
    sheets.selectRoutine("r-5")
    fields.save_week_starts_on("wednesday")
    wait_until(qapp, lambda: shell.session.week_start == "2026-11-04" and not shell.session.busy)
    settle(qapp, shell)
    pump(qapp)
    assert sheets.form["movedNote"] != ""
    sheets.toggleRoutineDay(5)
    pump(qapp)
    assert sheets.form["movedNote"] == ""
    assert not [day for day in sheets.form["days"] if day.get("moved")]
    assert _chip_name(shell, "routineDay5") == "Mon 9"


def test_two_moved_routine_days_share_one_note(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    from desktop.native import fields

    shell.session.routines["r-6"] = {
        "id": "r-6",
        "name": "Monday and Tuesday",
        "revision": 1,
        "blocks": [
            {
                "template_id": "t1",
                "title": "Long walk",
                "days": [0, 1],
                "start": "10:00",
                "duration_min": 60,
                "category": "exercise",
            }
        ],
    }
    sheets.openRoutines()
    pump(qapp)
    sheets.selectRoutine("r-6")
    fields.save_week_starts_on("wednesday")
    wait_until(qapp, lambda: shell.session.week_start == "2026-11-04" and not shell.session.busy)
    settle(qapp, shell)
    pump(qapp)
    form = sheets.form
    assert form["movedNote"] == (
        "Monday 2 and Tuesday 3 aren't in this week any more, "
        "so they moved to Monday 9 and Tuesday 10."
    )
    assert [day["value"] for day in form["days"] if day.get("moved")] == [5, 6]


def _monday_and_wednesday(shell: NativeWindow) -> None:
    shell.session.routines["r-4"] = {
        "id": "r-4",
        "name": "Monday and Wednesday",
        "revision": 1,
        "blocks": [
            {
                "template_id": "t1",
                "title": "Long walk",
                "days": [0, 2],
                "start": "10:00",
                "duration_min": 60,
                "category": "exercise",
            }
        ],
    }


def test_the_next_week_opened_under_the_sheet_marks_nothing(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    # The week still starts on Monday, so Monday 2 and Wednesday 4 are Monday 9 and Wednesday 11 of
    # the next week by the same weekday: no day moved, so nothing is marked or named.
    _monday_and_wednesday(shell)
    sheets.openRoutines()
    pump(qapp)
    sheets.selectRoutine("r-4")
    shell.session.load_week("2026-11-09")
    wait_until(qapp, lambda: shell.session.week_start == "2026-11-09" and not shell.session.busy)
    settle(qapp, shell)
    pump(qapp)
    form = sheets.form
    assert form["movedNote"] == ""
    assert [day["value"] for day in form["days"] if day["on"]] == [0, 2]
    assert not any(day.get("moved") for day in form["days"])


def test_a_second_switch_keeps_a_mark_the_student_has_not_touched(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    # Monday 2 moved to Monday 9 when the week began starting on Wednesday. Starting it on Thursday
    # (Thu 5 to Wed 11) keeps Monday 9, so its mark stays until the row is touched, and Wednesday 4
    # now moves to Wednesday 11: both are named.
    from desktop.native import fields

    _monday_and_wednesday(shell)
    sheets.openRoutines()
    pump(qapp)
    sheets.selectRoutine("r-4")
    fields.save_week_starts_on("wednesday")
    wait_until(qapp, lambda: shell.session.week_start == "2026-11-04" and not shell.session.busy)
    settle(qapp, shell)
    fields.save_week_starts_on("thursday")
    wait_until(qapp, lambda: shell.session.week_start == "2026-11-05" and not shell.session.busy)
    settle(qapp, shell)
    pump(qapp)
    form = sheets.form
    assert form["movedNote"] == (
        "Monday 2 and Wednesday 4 aren't in this week any more, so they moved to Monday 9 and "
        "Wednesday 11."
    )
    by_value = {day["value"]: day for day in form["days"]}
    assert (by_value[4]["moved"], by_value[4]["movedFrom"]) == (True, "Monday 2")
    assert (by_value[6]["moved"], by_value[6]["movedFrom"]) == (True, "Wednesday 4")


def test_a_mark_clears_when_a_week_from_the_same_first_day_opens(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    # Monday 2 moved to Monday 9 when the week began starting on Wednesday. Opening the next week
    # (Wed 11 to Tue 17, the same first day) is another week: the mark and note are gone.
    from desktop.native import fields

    _monday_and_wednesday(shell)
    sheets.openRoutines()
    pump(qapp)
    sheets.selectRoutine("r-4")
    fields.save_week_starts_on("wednesday")
    wait_until(qapp, lambda: shell.session.week_start == "2026-11-04" and not shell.session.busy)
    settle(qapp, shell)
    pump(qapp)
    assert sheets.form["movedNote"] != ""
    shell.session.load_week("2026-11-11")
    wait_until(qapp, lambda: shell.session.week_start == "2026-11-11" and not shell.session.busy)
    settle(qapp, shell)
    pump(qapp)
    assert sheets.form["movedNote"] == ""
    assert not any(day.get("moved") for day in sheets.form["days"])
