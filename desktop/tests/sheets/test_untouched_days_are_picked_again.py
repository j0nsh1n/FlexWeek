"""A sheet kept after Esc and opened again after the week start changed carries only the days the student
ticked, each on its weekday, with the moved mark and note. Days the student never touched (the row still
holds what the app put there when the sheet opened) are picked again for the new open week, as a fresh
sheet would, with no mark and no note.

The clock reads Thursday 5 November 2026, so the week from Monday 30 November has no today: a fresh sheet
there picks its first day, and from Wednesday that first day is Wednesday 2 December. A kept Monday 30
ticked by hand becomes Monday 7 December.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QDialog  # noqa: E402

from desktop.native.widgets import BlockDialog  # noqa: E402
from desktop.tests.light_app import window  # noqa: E402,F401
from desktop.tests.material_support import pump  # noqa: E402
from desktop.tests.sheets.support_material_sheet_fixtures import (  # noqa: E402,F401
    qapp,
    settle,
    sheets,
    shell,
)
from desktop.tests.sheets.test_fixed_time_discard_on_escape import (  # noqa: E402
    press_escape,
)
from desktop.tests.sheets.test_material_escape_keeps_the_typing import (  # noqa: E402,F401
    _picked,
    focused,
    open_add,
    type_title,
)
from desktop.tests.sheets.test_moved_days_across_months import (  # noqa: E402
    _go,
    _wednesday,
    press_escape_material,
)

MONDAY_NOTE = "Monday 30 November isn't in this week any more, so it moved to Monday 7 December."
TUESDAY_NOTE = "Tuesday 1 isn't in this week any more, so it moved to Tuesday 8."


def _tick_material_days(sheets, days: list[int]) -> None:
    for day in [item["value"] for item in sheets.form["days"] if item["on"]]:
        sheets.toggleDay(day)
    for day in days:
        sheets.toggleDay(day)


@pytest.mark.parametrize(
    "ticked, picked, note",
    [
        (None, [(0, "Wed 2")], ""),
        ([1], [(6, "Tue 8")], TUESDAY_NOTE),
        ([0, 2], [(0, "Wed 2"), (5, "Mon 7")], MONDAY_NOTE),
    ],
    ids=["untouched", "ticked", "mix"],
)
def test_material_block_carries_only_ticked_days(qapp, shell, focused, ticked, picked, note) -> None:
    sheets = focused
    _go(qapp, shell.session, "2026-11-30")
    open_add(sheets, "block")
    type_title(sheets, "Piano lesson")
    if ticked is not None:
        _tick_material_days(sheets, ticked)
    press_escape_material(shell)
    _wednesday(qapp, shell.session)
    settle(qapp, shell)
    open_add(sheets, "block")
    assert _picked(sheets, "block") == picked
    form = sheets.form
    assert form["movedNote"] == note
    assert [day["value"] for day in form["days"] if day.get("moved")] == (
        [] if not note else [value for value, _ in picked if value in (5, 6)]
    )


def test_material_homework_pin_untouched_is_picked_again(qapp, shell, focused) -> None:
    sheets = focused
    _go(qapp, shell.session, "2026-11-30")
    open_add(sheets, "homework")
    type_title(sheets, "Piano lesson")
    sheets.setText("when", "fixed")
    press_escape_material(shell)
    _wednesday(qapp, shell.session)
    settle(qapp, shell)
    open_add(sheets, "homework")
    form = sheets.form
    assert form["when"] == "fixed"
    assert _picked(sheets, "homework") == [(0, "Wed 2")]
    assert (form["whenMovedNote"], form["whenDayAccess"]) == ("", "")


def test_material_homework_pin_picked_by_hand_is_carried(qapp, shell, focused) -> None:
    sheets = focused
    _go(qapp, shell.session, "2026-11-30")
    open_add(sheets, "homework")
    type_title(sheets, "Piano lesson")
    sheets.setText("when", "fixed")
    sheets.setNumber("whenDay", 1)
    press_escape_material(shell)
    _wednesday(qapp, shell.session)
    settle(qapp, shell)
    open_add(sheets, "homework")
    form = sheets.form
    assert _picked(sheets, "homework") == [(6, "Tue 8")]
    assert form["whenMovedNote"] == TUESDAY_NOTE
    assert form["whenDayAccess"] == "Day, moved from Tuesday 1"


def test_material_routine_days_carry_only_the_ticked_ones(qapp, shell, sheets) -> None:
    routine = {
        "id": "r-8",
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
    _go(qapp, shell.session, "2026-11-30")
    sheets.openRoutines()
    pump(qapp, 40)
    shell.session.routines["r-8"] = routine
    sheets.selectRoutine("r-8")
    _wednesday(qapp, shell.session)
    settle(qapp, shell)
    shell.session.routines["r-8"] = routine
    pump(qapp)
    form = sheets.form
    assert [day["value"] for day in form["days"] if day["on"]] == [5, 6]
    assert form["movedNote"] == ""
    assert not [day for day in form["days"] if day.get("moved")]


def _widgets_pick(days: list[int] | None):
    def pick(dialog: QDialog) -> int:
        dialog.title.setText("Piano lesson")
        if days is not None:
            if isinstance(dialog, BlockDialog):
                for index, check in enumerate(dialog.days):
                    check.setChecked(index in days)
            else:
                dialog.when.setCurrentIndex(dialog.when.findData("fixed"))
                dialog.when_day.buttons[days[0]].click()
        elif not isinstance(dialog, BlockDialog):
            dialog.when.setCurrentIndex(dialog.when.findData("fixed"))
        press_escape(dialog)
        return int(dialog.result())

    return pick




