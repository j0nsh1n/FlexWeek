"""The block sheet's "Repeats every week" switch and Until row as the student sees them: the switch is on
the When step and the Edit sheet, Until shows only with the switch on, "No end" shows only with an Until,
Setup's own blocks never show the switch, and the Until sentence shows under the row."""

# ruff: noqa: F811
from __future__ import annotations

from datetime import date, timedelta

import pytest

pytest.importorskip("PySide6")

from desktop.native.calendar import date_for_day
from desktop.tests.material_support import named, pump
from desktop.tests.sheets.support_material_sheet_fixtures import (  # noqa: F401
    open_light,
    qapp,
    settle,
    sheets,
    shell,
)
from desktop.tests.sheets.support_soccer import soccer


def _visible(shell, name: str) -> bool:
    return any(item.isVisible() for item in named(shell._material_page.root, name))


def test_the_add_sheet_shows_the_switch_on_the_when_step_and_until_only_with_it_on(
    qapp, shell, sheets
) -> None:
    sheets.openBlock()
    pump(qapp, 20)
    assert not _visible(shell, "blockRepeat"), "the What step has no switch"
    sheets.setText("title", "Guitar")
    sheets.next()
    pump(qapp, 20)
    assert _visible(shell, "blockRepeat")
    assert not _visible(shell, "blockUntilRow")
    sheets.setFlag("repeat", True)
    pump(qapp, 20)
    assert _visible(shell, "blockUntilRow") and _visible(shell, "blockUntil")
    assert not _visible(shell, "blockUntilClear"), "no Until yet, so nothing to clear"
    sheets.setText("until", date_for_day(shell.session.week_start, 4))
    pump(qapp, 20)
    assert _visible(shell, "blockUntilClear")
    sheets.forceClose()


def test_setups_own_block_has_no_switch_and_a_plain_fixed_time_has_one(qapp, shell, sheets) -> None:
    sheets.editBlock("school", 0)
    pump(qapp, 20)
    assert not _visible(shell, "blockRepeat")
    sheets.forceClose()
    shell.session.add_block(soccer())
    shell.session.save()
    settle(qapp, shell)
    sheets.editBlock("soccer", 1)
    pump(qapp, 20)
    assert _visible(shell, "blockRepeat")
    sheets.forceClose()


def test_the_until_sentence_shows_under_the_row(qapp, shell, sheets) -> None:
    sheets.openBlock()
    sheets.setText("title", "Guitar")
    sheets.next()
    for day in [item["value"] for item in sheets.form["days"] if item["on"]]:
        sheets.toggleDay(day)
    sheets.toggleDay(4)
    sheets.setFlag("repeat", True)
    early = (date.fromisoformat(date_for_day(shell.session.week_start, 4)) - timedelta(days=1)).isoformat()
    sheets.setText("until", early)
    pump(qapp, 20)
    problems = [
        str(item.property("text"))
        for item in named(shell._material_page.root, "blockUntilProblem")
        if item.isVisible()
    ]
    assert problems and problems[0].startswith("Until can't be before the first day, ")
    sheets.forceClose()
