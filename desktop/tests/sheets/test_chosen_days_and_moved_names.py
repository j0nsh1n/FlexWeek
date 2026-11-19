"""Chosen days and moved-day names across a week-start switch.

A days row counts as touched once the student interacted with it, even if it ends on the value it opened with;
a grid-drawn day is the student's choice in both looks; month names are English whatever the computer's
language; Material's spoken chip names carry the destination month; Widgets does not say one note twice.

The clock reads Thursday 5 November 2026. The week from Monday 30 November has no today, so a fresh sheet
picks its first day there; from Wednesday that is Wednesday 2 December, and a chosen Monday 30 November
becomes Monday 7 December.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import locale

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.material.sheet_block import BlockDraft  # noqa: E402
from desktop.native.material.sheet_homework import HomeworkDraft  # noqa: E402
from desktop.native.sheet_rules import moved_day_names  # noqa: E402
from desktop.native.widgets import BlockDialog, HomeworkDialog  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import window  # noqa: E402,F401
from desktop.tests.material_support import pump  # noqa: E402
from desktop.tests.sheets.support_material_sheet_fixtures import (  # noqa: E402,F401
    qapp,
    settle,
    sheets,
    shell,
)
from desktop.tests.sheets.test_material_escape_keeps_the_typing import (  # noqa: E402,F401
    _qml_name,
    focused,
    open_add,
    type_title,
)
from desktop.tests.sheets.test_moved_days_across_months import (  # noqa: E402
    CROSSING,
    _go,
    _wednesday,
    press_escape_material,
)

DEC_7 = "Monday 7 December, moved from Monday 30 November"


@pytest.mark.parametrize("kind", ["block", "homework"])
@pytest.mark.parametrize("choice", ["untouched", "different", "returned"])
def test_material_choice_survives_a_week_start_switch(qapp, shell, kind: str, choice: str) -> None:
    _go(qapp, shell.session, "2026-11-30")
    if kind == "block":
        draft = BlockDraft(shell.session)
        assert draft.days == [0]
        if choice != "untouched":
            draft.toggle_day(0)
            draft.toggle_day(1)
        if choice == "returned":
            draft.toggle_day(1)
            draft.toggle_day(0)
    else:
        draft = HomeworkDraft(shell.session)
        assert draft.when_day == 0
        draft.set("when", "fixed")
        if choice != "untouched":
            draft.set("whenDay", 1)
        if choice == "returned":
            draft.set("whenDay", 0)
    _wednesday(qapp, shell.session)
    draft.follow_week([0] if kind == "block" else 0)
    actual = draft.days if kind == "block" else [draft.when_day]
    expected = {"untouched": [0], "different": [6], "returned": [5]}[choice]
    assert actual == expected, f"{kind} {choice}: got {actual}"
    note = draft._moved_note
    if choice == "returned":
        assert note == CROSSING










def test_month_names_are_english_under_another_language() -> None:
    saved = locale.setlocale(locale.LC_TIME)
    try:
        try:
            locale.setlocale(locale.LC_TIME, "de_DE.utf8")
        except locale.Error:
            pytest.skip("no German locale installed here")
        assert moved_day_names(0, "2026-11-30", 5, "2026-12-02") == (
            "Monday 30 November",
            "Monday 7 December",
        )
    finally:
        locale.setlocale(locale.LC_TIME, saved)


def test_material_block_chip_names_both_months(qapp, shell, focused) -> None:
    sheets = focused
    _go(qapp, shell.session, "2026-11-30")
    open_add(sheets, "block")
    type_title(sheets, "Piano lesson")
    for day in [item["value"] for item in sheets.form["days"] if item["on"]]:
        sheets.toggleDay(day)
    sheets.toggleDay(0)
    sheets.toggleDay(2)
    press_escape_material(shell)
    _wednesday(qapp, shell.session)
    settle(qapp, shell)
    open_add(sheets, "block")
    assert _qml_name(shell, "blockDay5") == DEC_7
    assert _qml_name(shell, "blockDay0") == "Wed 2"


def test_material_routine_chip_names_both_months(qapp, shell, sheets) -> None:
    routine = {
        "id": "r-11",
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
    _go(qapp, shell.session, "2026-11-30")
    sheets.openRoutines()
    pump(qapp, 40)
    shell.session.routines["r-11"] = routine
    sheets.selectRoutine("r-11")
    sheets.toggleRoutineDay(2)
    _wednesday(qapp, shell.session)
    settle(qapp, shell)
    shell.session.routines["r-11"] = routine
    pump(qapp)
    assert _qml_name(shell, "routineDay5") == DEC_7


def test_material_homework_day_names_both_months(qapp, shell, focused) -> None:
    sheets = focused
    _go(qapp, shell.session, "2026-11-30")
    open_add(sheets, "homework")
    type_title(sheets, "Piano lesson")
    sheets.setText("when", "fixed")
    sheets.setNumber("whenDay", 1)
    sheets.setNumber("whenDay", 0)
    press_escape_material(shell)
    _wednesday(qapp, shell.session)
    settle(qapp, shell)
    open_add(sheets, "homework")
    name = _qml_name(shell, "homeworkWhenDay")
    assert "Monday 30 November" in name and "Monday 7 December" in name, name


@pytest.mark.parametrize("sheet", [BlockDialog, HomeworkDialog])
def test_widgets_the_same_note_is_said_once(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch, sheet
) -> None:
    said: list[str] = []
    monkeypatch.setattr("desktop.native.widgets.announce", lambda _widget, text, **_kw: said.append(text))
    dialog = sheet(window)
    try:
        dialog.show()
        pump(qapp)
        dialog.show_moved_days([(5, "Monday 2", "Monday 9")])
        dialog.show_moved_days([(5, "Monday 2", "Monday 9")])
        assert len(said) == 1, said
        dialog.show_moved_days([(5, "Monday 2", "Monday 9"), (6, "Tuesday 3", "Tuesday 10")])
        assert len(said) == 2, said
    finally:
        dialog.reject()
