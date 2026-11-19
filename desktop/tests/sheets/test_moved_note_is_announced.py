"""A screen reader reads the moved-day note out when it appears (or changes) in a sheet that is already
open, once and politely. It does not repeat the note when the sheet opens with it already there (the
sheet is read with its note) and says nothing when the note clears.

The Material test hook is `announce` in the sheets bridge, the same function the Widgets sheets call
(`desktop.native.widgets.announce`). The clock reads Thursday 5 November 2026: the week from Monday 2
becomes Wed 4 to Tue 10 from Wednesday and Thu 5 to Wed 11 from Thursday.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

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
    focused,
    open_add,
    type_title,
)
from desktop.tests.sheets.test_moved_days_across_months import press_escape_material  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402

FIRST = "Monday 2 isn't in this week any more, so it moved to Monday 9."
SECOND = "Monday 2 and Wednesday 4 aren't in this week any more, so they moved to Monday 9 and Wednesday 11."


def _record(monkeypatch: pytest.MonkeyPatch, target: str) -> list[tuple[str, bool]]:
    said: list[tuple[str, bool]] = []

    def record(_widget, text, assertive=False) -> None:
        said.append((text, assertive))

    monkeypatch.setattr(target, record)
    return said


def _start_on(qapp: QApplication, session, day: str, week: str) -> None:
    from desktop.native import fields

    fields.save_week_starts_on(day)
    wait_until(qapp, lambda: session.week_start == week and not session.busy)


def _routine() -> dict:
    return {
        "id": "r-7",
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


def test_material_routines_note_is_announced_when_it_appears_and_when_it_changes(
    qapp, shell, sheets, monkeypatch: pytest.MonkeyPatch
) -> None:
    said = _record(monkeypatch, "desktop.native.material.bridge_sheets.announce")
    shell.session.routines["r-7"] = _routine()
    sheets.openRoutines()
    pump(qapp)
    sheets.selectRoutine("r-7")
    sheets.toggleRoutineDay(4)
    assert said == [], "nothing moved yet, so nothing is said"
    _start_on(qapp, shell.session, "wednesday", "2026-11-04")
    settle(qapp, shell)
    pump(qapp)
    assert said == [(FIRST, False)]
    assert sheets.form["movedNote"] == FIRST
    _start_on(qapp, shell.session, "thursday", "2026-11-05")
    settle(qapp, shell)
    pump(qapp)
    assert said[1:] == [(SECOND, False)]
    assert sheets.form["movedNote"] == SECOND
    before = len(said)
    sheets.toggleRoutineDay(4)
    pump(qapp)
    assert sheets.form["movedNote"] == ""
    assert len(said) == before, "a note that clears is not read out"


def test_material_sheet_opened_with_its_note_does_not_announce_it(
    qapp, shell, focused, monkeypatch: pytest.MonkeyPatch
) -> None:
    said = _record(monkeypatch, "desktop.native.material.bridge_sheets.announce")
    sheets = focused
    open_add(sheets, "block")
    type_title(sheets, "Piano lesson")
    for day in [item["value"] for item in sheets.form["days"] if item["on"]]:
        sheets.toggleDay(day)
    sheets.toggleDay(0)
    press_escape_material(shell)
    _start_on(qapp, shell.session, "wednesday", "2026-11-04")
    settle(qapp, shell)
    open_add(sheets, "block")
    assert sheets.form["movedNote"] == FIRST
    assert said == [], "the note is read with the sheet, not again on top of it"


@pytest.mark.parametrize("sheet", [BlockDialog, HomeworkDialog])
def test_widgets_note_is_announced_when_it_appears_in_an_open_sheet(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch, sheet
) -> None:
    said = _record(monkeypatch, "desktop.native.widgets.announce")
    dialog = sheet(window)
    try:
        dialog.show()
        pump(qapp)
        dialog.show_moved_days([(5, "Monday 2", "Monday 9")])
        assert said == [(FIRST, False)]
        dialog.show_moved_days([])
        assert said == [(FIRST, False)], "a note that clears is not read out"
    finally:
        dialog.reject()
