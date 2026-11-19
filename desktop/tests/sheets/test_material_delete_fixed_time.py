"""Deleting a fixed time on Material: it asks first, says exactly what goes, does nothing when refused, and
the notice that follows offers Undo."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import date

import pytest
from PySide6.QtWidgets import QApplication

pytest.importorskip("PySide6")

from desktop.native.calendar import date_for_day
from desktop.tests.material_support import pump
from desktop.tests.sheets.support_material_sheet_fixtures import (  # noqa: F401
    open_light,
    qapp,
    sheets,
    shell,
)
from desktop.tests.sheets.support_soccer import soccer
from desktop.tests.waiting import wait_until


def _add_soccer(qapp, shell) -> None:
    shell.session.add_block(soccer())
    shell.session.save()
    wait_until(qapp, lambda: not shell.session.busy and not shell.session.dirty)


def _ask_from_the_sheet(sheets, scope: str, day: int = 3) -> dict:
    sheets.editBlock("soccer", day)
    pump(QApplication.instance(), 5)
    sheets.setText("scope", scope)
    sheets.remove()
    return dict(sheets.ask)


def _soccer_ids(shell) -> list[str]:
    return [block["id"] for block in shell.session.blocks if block["id"] == "soccer"]


def test_delete_asks_first_and_does_nothing_when_refused(qapp, shell, sheets) -> None:
    _add_soccer(qapp, shell)
    ask = _ask_from_the_sheet(sheets, "series")
    assert ask["title"] == "Delete fixed time"
    assert ask["body"] == "Delete Soccer practice on every Tue and Thu this week? You can undo this."
    assert [answer["label"] for answer in ask["answers"]] == ["Cancel", "Delete"]
    sheets.answer("stay")
    pump(qapp, 10)
    assert _soccer_ids(shell) == ["soccer"], "refusing deletes nothing"
    assert sheets.kind == "block", "refusing leaves the editor open"


def test_deleting_one_day_names_the_day_and_its_date(qapp, shell, sheets) -> None:
    _add_soccer(qapp, shell)
    ask = _ask_from_the_sheet(sheets, "occurrence")
    occurrence = date.fromisoformat(date_for_day(shell.session.week_start, 3))
    stamp = f"{occurrence.day} {occurrence.strftime('%b')}"
    assert ask["body"] == f"Delete Soccer practice on Thursday {stamp} only? You can undo this."


def test_a_deleted_block_can_be_undone_from_the_notice(qapp, shell, sheets) -> None:
    _add_soccer(qapp, shell)
    _ask_from_the_sheet(sheets, "series")
    sheets.answer("delete")
    wait_until(qapp, lambda: not shell.session.busy and not shell.session.dirty)
    assert _soccer_ids(shell) == []
    assert sheets.notice == "Deleted Soccer practice from this week."
    assert sheets.noticeUndo is True
    sheets.undoNotice()
    wait_until(qapp, lambda: _soccer_ids(shell) == ["soccer"])
