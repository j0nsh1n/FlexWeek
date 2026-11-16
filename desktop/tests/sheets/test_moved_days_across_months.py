"""The note under a day row that a week-start switch moved names the month when the move crosses into
another month: "Monday 30 November isn't in this week any more, so it moved to Monday 7 December." A
pair inside one month stays "Monday 2 ... Monday 9" (the tests beside this one pin that). Each pair of a
longer note is judged on its own dates, and the mark's accessible name follows its pair.

The clock reads Thursday 5 November 2026. The week from Monday 30 November holds Monday 30 and Tuesday 1
December; from Wednesday it is Wed 2 to Tue 8 December, so Monday 30 becomes Monday 7 December and Tuesday 1
becomes Tuesday 8 December.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialog, QLabel  # noqa: E402

from desktop.native.widgets import BlockDialog  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import window  # noqa: E402,F401
from desktop.tests.material_support import pump  # noqa: E402
from desktop.tests.sheets.support_material_sheet_fixtures import (  # noqa: E402,F401
    qapp,
    settle,
    sheets,
    shell,
)
from desktop.tests.sheets.test_fixed_time_discard_on_escape import (  # noqa: E402
    Script,
    only_look,
    press_escape,
)
from desktop.tests.sheets.test_material_escape_keeps_the_typing import (  # noqa: E402,F401
    _qml_name,
    focused,
    open_add,
    type_title,
)
from desktop.tests.waiting import wait_until  # noqa: E402

CROSSING = "Monday 30 November isn't in this week any more, so it moved to Monday 7 December."
TWO_PAIRS = (
    "Monday 30 November and Tuesday 1 aren't in this week any more, "
    "so they moved to Monday 7 December and Tuesday 8."
)


def _go(qapp: QApplication, session, week: str) -> None:
    session.load_week(week)
    wait_until(qapp, lambda: session.week_start == week and not session.busy)


def _wednesday(qapp: QApplication, session, week: str = "2026-12-02") -> None:
    from desktop.native import fields

    fields.save_week_starts_on("wednesday")
    wait_until(qapp, lambda: session.week_start == week and not session.busy)


def _tick_widgets(days: list[int]):
    def pick(dialog: QDialog) -> int:
        dialog.title.setText("Piano lesson")
        if isinstance(dialog, BlockDialog):
            for index, check in enumerate(dialog.days):
                check.setChecked(index in days)
        else:
            dialog.when.setCurrentIndex(dialog.when.findData("fixed"))
            dialog.when_day.buttons[days[0]].click()
        press_escape(dialog)
        return int(dialog.result())

    return pick


@pytest.mark.parametrize(
    "days, note, pills",
    [
        ([0, 2], CROSSING, {5: "Monday 7 December, moved from Monday 30 November"}),
        (
            [0, 1],
            TWO_PAIRS,
            {
                5: "Monday 7 December, moved from Monday 30 November",
                6: "Tuesday 8, moved from Tuesday 1",
            },
        ),
    ],
)
def test_widgets_block_names_the_month_where_a_move_crosses_it(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch, days, note, pills
) -> None:
    seen: dict = {}

    def inspect(dialog: QDialog) -> int:
        seen["note"] = dialog.findChild(QLabel, "blockMovedNote").text()
        seen["pills"] = {day: dialog.day_picker.buttons[day].accessibleName() for day in pills}
        return only_look(dialog)

    Script("block", monkeypatch, _tick_widgets(days), inspect)
    _go(qapp, window.session, "2026-11-30")
    window._add_fixed()
    pump(qapp)
    _wednesday(qapp, window.session)
    window._add_fixed()
    pump(qapp)
    assert seen["note"] == note
    assert seen["pills"] == pills


def test_widgets_homework_pin_names_the_month_where_the_move_crosses_it(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict = {}

    def inspect(dialog: QDialog) -> int:
        seen["note"] = dialog.findChild(QLabel, "homeworkMovedNote").text()
        seen["pill"] = dialog.when_day.buttons[5].accessibleName()
        return only_look(dialog)

    Script("homework", monkeypatch, _tick_widgets([0]), inspect)
    _go(qapp, window.session, "2026-11-30")
    window._add_homework()
    pump(qapp)
    _wednesday(qapp, window.session)
    window._add_homework()
    pump(qapp)
    assert seen["note"] == CROSSING
    assert seen["pill"] == "Monday 7 December, moved from Monday 30 November"


@pytest.mark.parametrize(
    "days, note",
    [([0, 2], CROSSING), ([0, 1], TWO_PAIRS)],
)
def test_material_block_names_the_month_where_a_move_crosses_it(qapp, shell, focused, days, note) -> None:
    sheets = focused
    _go(qapp, shell.session, "2026-11-30")
    open_add(sheets, "block")
    type_title(sheets, "Piano lesson")
    for day in [item["value"] for item in sheets.form["days"] if item["on"]]:
        sheets.toggleDay(day)
    for day in days:
        sheets.toggleDay(day)
    press_escape_material(shell)
    _wednesday(qapp, shell.session)
    settle(qapp, shell)
    open_add(sheets, "block")
    form = sheets.form
    assert form["movedNote"] == note
    by_value = {day["value"]: day for day in form["days"]}
    assert by_value[5]["movedFrom"] == "Monday 30 November"
    assert _qml_name(shell, "blockDay5") == "Monday 7 December, moved from Monday 30 November"
    if days == [0, 1]:
        assert by_value[6]["movedFrom"] == "Tuesday 1"


def test_material_homework_pin_names_the_month_where_the_move_crosses_it(qapp, shell, focused) -> None:
    """Tuesday 24 November pinned in the week from Monday 23; from Wednesday that week is Wed 25 to Tue 1
    December, so the pin becomes Tuesday 1 December."""
    sheets = focused
    _go(qapp, shell.session, "2026-11-23")
    open_add(sheets, "homework")
    type_title(sheets, "Piano lesson")
    sheets.setText("when", "fixed")
    sheets.setNumber("whenDay", 1)
    press_escape_material(shell)
    _wednesday(qapp, shell.session, "2026-11-25")
    settle(qapp, shell)
    open_add(sheets, "homework")
    form = sheets.form
    assert form["whenMovedNote"] == (
        "Tuesday 24 November isn't in this week any more, so it moved to Tuesday 1 December."
    )
    assert form["whenDayAccess"] == "Day, moved from Tuesday 24 November to Tuesday 1 December"


def test_material_routine_days_name_the_month_where_a_move_crosses_it(qapp, shell, sheets) -> None:
    routine = {
        "id": "r-9",
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
    shell.session.routines["r-9"] = routine
    sheets.selectRoutine("r-9")
    sheets.toggleRoutineDay(2)
    _wednesday(qapp, shell.session)
    settle(qapp, shell)
    shell.session.routines["r-9"] = routine
    pump(qapp)
    assert sheets.form["movedNote"] == TWO_PAIRS
    by_value = {day["value"]: day for day in sheets.form["days"]}
    assert by_value[5]["movedFrom"] == "Monday 30 November"
    assert by_value[6]["movedFrom"] == "Tuesday 1"


def press_escape_material(shell) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    QTest.keyClick(shell._material_page._quick, Qt.Key.Key_Escape)
    pump(QApplication.instance(), 30)
