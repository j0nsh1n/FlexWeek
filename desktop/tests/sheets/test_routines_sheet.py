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
