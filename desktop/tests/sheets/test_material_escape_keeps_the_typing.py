"""Esc on a new Add homework or Add fixed time sheet with typing closes it at once, with no question, and
the next Add of the same kind opens with what was typed (Jonathan, 2026-11-10). Cancel and a tap on the dim
area still ask "Discard your changes?"; Edit sheets are unchanged; Save and Discard end what was kept.

Expected values come from the requirement. The one clock reads Thursday 19:00.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.tests.material_support import named, pump  # noqa: E402
from desktop.tests.sheets.support_material_sheet_fixtures import (  # noqa: E402,F401
    open_light,
    qapp,
    settle,
    sheets,
    shell,
)
from desktop.tests.waiting import wait_until  # noqa: E402

OPEN = {"homework": "openHomework", "block": "openBlock"}
CANCEL = {"homework": "homeworkCancel", "block": "blockCancel"}
KINDS = ["homework", "block"]


def open_add(sheets, kind: str) -> None:
    getattr(sheets, OPEN[kind])()
    pump(QApplication.instance(), 20)
    assert sheets.kind == kind


def title_now(sheets) -> str:
    return str(sheets.form["title"])


def type_title(sheets, text: str) -> None:
    sheets.setText("title", text)


def press_escape(shell) -> None:
    QTest.keyClick(shell._material_page._quick, Qt.Key.Key_Escape)
    pump(QApplication.instance(), 30)


@pytest.fixture()
def focused(shell, sheets):
    shell.activateWindow()
    shell._material_page._quick.setFocus()
    pump(QApplication.instance(), 20)
    return sheets


@pytest.mark.parametrize("kind", KINDS)
def test_escape_with_typing_closes_at_once_and_the_next_add_shows_it(qapp, shell, focused, kind: str) -> None:
    sheets = focused
    open_add(sheets, kind)
    type_title(sheets, "Piano lesson")
    press_escape(shell)
    assert sheets.kind == ""
    assert sheets.ask == {}
    open_add(sheets, kind)
    assert title_now(sheets) == "Piano lesson"


@pytest.mark.parametrize("kind, other", [("homework", "block"), ("block", "homework")])
def test_the_other_kinds_add_opens_empty(qapp, shell, focused, kind: str, other: str) -> None:
    sheets = focused
    open_add(sheets, kind)
    type_title(sheets, "Piano lesson")
    press_escape(shell)
    open_add(sheets, other)
    assert title_now(sheets) == ""


@pytest.mark.parametrize("kind", KINDS)
def test_escape_with_nothing_typed_closes_and_keeps_nothing(qapp, shell, focused, kind: str) -> None:
    sheets = focused
    open_add(sheets, kind)
    press_escape(shell)
    assert sheets.kind == ""
    assert sheets.ask == {}
    open_add(sheets, kind)
    assert title_now(sheets) == ""


@pytest.mark.parametrize("kind", KINDS)
def test_cancel_still_asks_and_discard_leaves_the_next_add_empty(qapp, shell, focused, kind: str) -> None:
    sheets = focused
    open_add(sheets, kind)
    type_title(sheets, "Piano lesson")
    sheets.closeSheet()  # what the Cancel button calls
    assert sheets.ask.get("id") == "discard"
    sheets.answer("discard")
    assert sheets.kind == ""
    open_add(sheets, kind)
    assert title_now(sheets) == ""


@pytest.mark.parametrize("kind", KINDS)
def test_the_cancel_button_asks_while_something_is_typed(qapp, shell, focused, kind: str) -> None:
    sheets = focused
    root = shell._material_page.root
    open_add(sheets, kind)
    type_title(sheets, "Piano lesson")
    pump(QApplication.instance(), 40)
    button = named(root, CANCEL[kind])[0]
    centre = button.mapToScene(button.boundingRect().center()).toPoint()
    quick = shell._material_page._quick
    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, pos=QPoint(centre.x(), centre.y()))
    wait_until(None, lambda: sheets.ask.get("id") == "discard", what="the Discard question")
    assert sheets.kind == kind


@pytest.mark.parametrize("kind", KINDS)
def test_a_tap_on_the_dim_area_still_asks(qapp, shell, focused, kind: str) -> None:
    sheets = focused
    open_add(sheets, kind)
    type_title(sheets, "Piano lesson")
    pump(QApplication.instance(), 40)
    QTest.mouseClick(shell._material_page._quick, Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
    wait_until(None, lambda: sheets.ask.get("id") == "discard", what="the Discard question")


def test_after_a_save_the_next_add_homework_is_empty(qapp, shell, focused) -> None:
    sheets = focused
    open_add(sheets, "homework")
    type_title(sheets, "Lab report")
    press_escape(shell)
    open_add(sheets, "homework")
    assert title_now(sheets) == "Lab report"
    sheets.save()
    settle(qapp, shell)
    assert sheets.kind == ""
    open_add(sheets, "homework")
    assert title_now(sheets) == ""


def test_after_a_save_the_next_add_fixed_time_is_empty(qapp, shell, focused) -> None:
    sheets = focused
    open_add(sheets, "block")
    type_title(sheets, "Piano lesson")
    press_escape(shell)
    open_add(sheets, "block")
    assert title_now(sheets) == "Piano lesson"
    for _ in range(6):
        if sheets.kind != "block":
            break
        sheets.save() if sheets.form["step"] in (-1, 2, 3) else sheets.next()
        settle(qapp, shell)
    assert sheets.kind == "", "the fixed time saved"
    open_add(sheets, "block")
    assert title_now(sheets) == ""


def test_an_edit_sheet_still_asks_on_escape_and_keeps_nothing(qapp, shell, focused) -> None:
    sheets = focused
    sheets.editHomework("essay")
    pump(QApplication.instance(), 20)
    type_title(sheets, "History essay, second draft")
    press_escape(shell)
    wait_until(None, lambda: sheets.ask.get("id") == "discard", what="the Discard question")
    assert sheets.kind == "homework"
    sheets.answer("discard")
    open_add(sheets, "homework")
    assert title_now(sheets) == ""


def test_a_new_account_does_not_see_the_typing_of_the_last(qapp, shell, focused) -> None:
    sheets = focused
    open_add(sheets, "homework")
    type_title(sheets, "Piano lesson")
    press_escape(shell)
    shell.session.account_changed.emit(None)
    open_add(sheets, "homework")
    assert title_now(sheets) == ""


def _pick_friday(sheets, kind: str) -> None:
    """Friday 6 November is day 4 of the week from Monday 2 November; today, Thursday 5, is day 3."""
    if kind == "block":
        sheets.toggleDay(4)
        sheets.toggleDay(3)
    else:
        sheets.setText("when", "fixed")
        sheets.setNumber("whenDay", 4)


def _picked(sheets, kind: str) -> list[tuple[int, str]]:
    form = sheets.form
    if kind == "block":
        return [(day["value"], f"{day['label']} {day['date']}") for day in form["days"] if day["on"]]
    return [(form["whenDay"], form["dayOptions"][form["whenDay"]]["label"])]


@pytest.mark.parametrize("kind", KINDS)
def test_a_day_kept_by_escape_keeps_its_weekday_when_the_week_start_changes(
    qapp, shell, focused, kind: str
) -> None:
    """Friday 6 is day 2 of the week from Wednesday 4 November, so the kept Friday is still Friday 6 after
    Wednesday is picked, and the closed sheet still counts as typed in."""
    from desktop.native import fields

    sheets = focused
    open_add(sheets, kind)
    type_title(sheets, "Piano lesson")
    _pick_friday(sheets, kind)
    assert _picked(sheets, kind) == [(4, "Fri 6")]
    press_escape(shell)
    assert sheets.kind == ""
    fields.save_week_starts_on("wednesday")
    wait_until(qapp, lambda: shell.session.week_start == "2026-11-04" and not shell.session.busy)
    settle(qapp, shell)
    open_add(sheets, kind)
    assert title_now(sheets) == "Piano lesson"
    assert _picked(sheets, kind) == [(2, "Fri 6")]
    sheets.closeSheet()  # what the Cancel button calls
    assert sheets.ask.get("id") == "discard"


@pytest.mark.parametrize("kind", KINDS)
def test_a_kept_sheet_reopened_in_the_new_week_closes_at_once_when_its_typing_is_undone(
    qapp, shell, focused, kind: str
) -> None:
    """The kept sheet opened on today, Thursday 5 (day 3 of the week from Monday, day 1 of the week from
    Wednesday). Back on Thursday with the title cleared, it shows what it opened with, so Cancel closes it
    with no question."""
    from desktop.native import fields

    sheets = focused
    open_add(sheets, kind)
    type_title(sheets, "Piano lesson")
    _pick_friday(sheets, kind)
    press_escape(shell)
    fields.save_week_starts_on("wednesday")
    wait_until(qapp, lambda: shell.session.week_start == "2026-11-04" and not shell.session.busy)
    settle(qapp, shell)
    open_add(sheets, kind)
    if kind == "block":
        sheets.toggleDay(1)
        sheets.toggleDay(2)
    else:
        sheets.setNumber("whenDay", 1)
        sheets.setText("when", "plan")
    type_title(sheets, "")
    sheets.closeSheet()  # what the Cancel button calls
    assert sheets.ask == {}
    assert sheets.kind == ""


def _qml_name(shell, name: str) -> str:
    from PySide6.QtGui import QAccessible

    found = named(shell._material_page.root, name)
    assert found, name
    face = QAccessible.queryAccessibleInterface(found[0])
    assert face is not None, name
    return face.text(QAccessible.Text.Name)


def test_a_kept_block_reopened_in_the_new_week_marks_the_moved_day(
    qapp, shell, focused
) -> None:
    """Monday 2 is ticked in the week from Monday 2 November. From Wednesday the week is Wed 4 to
    Tue 10, so the kept Monday is Monday 9: marked, named, and announced until touched."""
    from desktop.native import fields

    sheets = focused
    open_add(sheets, "block")
    type_title(sheets, "Piano lesson")
    sheets.toggleDay(0)
    sheets.toggleDay(3)
    assert _picked(sheets, "block") == [(0, "Mon 2")]
    press_escape(shell)
    assert sheets.kind == ""
    fields.save_week_starts_on("wednesday")
    wait_until(qapp, lambda: shell.session.week_start == "2026-11-04" and not shell.session.busy)
    settle(qapp, shell)
    open_add(sheets, "block")
    assert _picked(sheets, "block") == [(5, "Mon 9")]
    form = sheets.form
    assert form["movedNote"] == "Monday 2 isn't in this week any more, so it moved to Monday 9."
    by_value = {day["value"]: day for day in form["days"]}
    assert by_value[5]["moved"] and by_value[5]["movedFrom"] == "Monday 2"
    assert _qml_name(shell, "blockDay5") == "Mon 9, moved from Monday 2"
    assert _qml_name(shell, "blockMovedNote") == form["movedNote"]
    sheets.toggleDay(5)
    pump(qapp)
    assert sheets.form["movedNote"] == ""
    assert not [day for day in sheets.form["days"] if day.get("moved")]
    assert _qml_name(shell, "blockDay5") == "Mon 9"


def test_a_kept_homework_reopened_in_the_new_week_names_the_moved_pin(
    qapp, shell, focused
) -> None:
    """The pinned Monday 2 becomes Monday 9: no chips, so the dropdown's name and the note under
    the When row carry it until the student picks another day."""
    from desktop.native import fields

    sheets = focused
    open_add(sheets, "homework")
    type_title(sheets, "Piano lesson")
    sheets.setText("when", "fixed")
    sheets.setNumber("whenDay", 0)
    assert _picked(sheets, "homework") == [(0, "Mon 2")]
    press_escape(shell)
    assert sheets.kind == ""
    fields.save_week_starts_on("wednesday")
    wait_until(qapp, lambda: shell.session.week_start == "2026-11-04" and not shell.session.busy)
    settle(qapp, shell)
    open_add(sheets, "homework")
    assert _picked(sheets, "homework") == [(5, "Mon 9")]
    form = sheets.form
    assert form["whenMovedNote"] == "Monday 2 isn't in this week any more, so it moved to Monday 9."
    assert form["whenDayAccess"] == "Day, moved from Monday 2"
    assert _qml_name(shell, "homeworkWhenDay") == "Day, moved from Monday 2, Mon 9"
    assert _qml_name(shell, "homeworkMovedNote") == form["whenMovedNote"]
    sheets.setNumber("whenDay", 4)
    pump(qapp)
    assert sheets.form["whenMovedNote"] == ""
    assert sheets.form["whenDayAccess"] == ""
