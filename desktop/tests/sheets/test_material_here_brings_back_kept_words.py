"""Material: Esc on a new Add fixed time or Add homework sheet keeps what was typed, and the next one of the
same kind opens with it however it is opened, including "Add ... here" on free time in the week. The time
the student clicked is the one the sheet shows."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import pump
from desktop.tests.sheets.support_material_sheets import bridge, material_week
from desktop.tests.window_support import qapp, settled  # noqa: F401

SATURDAY = 5
TEN, ELEVEN, NOON, ONE = 600, 660, 720, 780


def test_add_fixed_time_here_brings_back_the_words_kept_by_esc(qapp, window: NativeWindow) -> None:
    material_week(qapp, window)
    sheets = bridge(window).sheets
    sheets.openBlockAt(SATURDAY, TEN, ELEVEN)
    sheets.setText("title", "Dentist")
    sheets.escapeSheet()
    pump(qapp)
    assert sheets.kind == ""

    sheets.openBlockAt(SATURDAY, NOON, ONE)

    form = sheets.form
    assert form["title"] == "Dentist"
    # The time just clicked wins over the one the kept sheet had.
    assert (form["start"], form["end"]) == ("12:00", ONE)
    assert [day["on"] for day in form["days"]] == [index == SATURDAY for index in range(7)]


def test_add_homework_here_brings_back_the_words_kept_by_esc(qapp, window: NativeWindow) -> None:
    material_week(qapp, window)
    sheets = bridge(window).sheets
    sheets.openHomeworkAt(SATURDAY, TEN, ELEVEN)
    sheets.setText("title", "Chem lab")
    sheets.escapeSheet()
    pump(qapp)
    assert sheets.kind == ""

    sheets.openHomeworkAt(SATURDAY, NOON, ONE)

    form = sheets.form
    assert form["title"] == "Chem lab"
    assert (form["when"], form["whenDay"], form["whenTime"]) == ("fixed", SATURDAY, "12:00")


def test_the_kept_words_are_used_once(qapp, window: NativeWindow) -> None:
    material_week(qapp, window)
    sheets = bridge(window).sheets
    sheets.openBlockAt(SATURDAY, TEN, ELEVEN)
    sheets.setText("title", "Dentist")
    sheets.escapeSheet()
    sheets.openBlockAt(SATURDAY, NOON, ONE)
    sheets.forceClose()

    sheets.openBlockAt(SATURDAY, NOON, ONE)

    assert sheets.form["title"] != "Dentist"
