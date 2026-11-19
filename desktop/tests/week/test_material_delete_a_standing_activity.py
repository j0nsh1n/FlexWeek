"""Deleting School or a Setup activity on Material asks "This day only", "This week only" or "This week and
later", says what went, offers Undo only where Undo can work, and does nothing when refused."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import date

import pytest

pytest.importorskip("PySide6")

from desktop.native.calendar import date_for_day
from desktop.tests.material_support import pump
from desktop.tests.sheets.support_material_sheet_fixtures import (  # noqa: F401
    open_light,
    qapp,
    sheets,
    shell,
)
from desktop.tests.waiting import wait_until

SOCCER = {
    "id": "activity-1",
    "title": "Soccer",
    "kind": "locked",
    "category": "extra",
    "start": "16:00",
    "duration_min": 90,
    "days": [1, 3],
}


@pytest.fixture()
def soccer_week(qapp, shell, sheets):
    """Setup's Soccer in the open week, Tuesday and Thursday."""
    shell.session.set_setup_blocks([dict(SOCCER)])
    shell.session.save()
    wait_until(qapp, lambda: not shell.session.busy and not shell.session.dirty)
    return shell


def _soccer(shell) -> dict | None:
    return next((b for b in shell.session.blocks if b["id"] == "activity-1"), None)


def _settled(qapp, shell) -> None:
    wait_until(qapp, lambda: not shell.session.busy and not shell.session.dirty)
    pump(qapp, 10)


def test_this_week_only_keeps_soccer_here_missed_on_every_day_and_undo_brings_it_back(
    qapp, soccer_week, sheets
) -> None:
    sheets.askDeleteBlock("activity-1", -1)
    assert sheets.ask["id"] == "delete-block"
    sheets.answer("week")
    _settled(qapp, soccer_week)
    assert _soccer(soccer_week)["missed_days"] == [1, 3]
    assert sheets.notice == "Deleted Soccer from this week." and sheets.noticeUndo is True
    sheets.undoNotice()
    _settled(qapp, soccer_week)
    assert not _soccer(soccer_week).get("missed_days")


def test_this_week_and_later_takes_soccer_out_and_says_so_with_no_undo(qapp, soccer_week, sheets) -> None:
    sheets.askDeleteBlock("activity-1", -1)
    sheets.answer("every")
    _settled(qapp, soccer_week)
    assert _soccer(soccer_week) is None
    assert sheets.notice == "Deleted Soccer from this week and every week after."
    assert sheets.noticeUndo is False, "the irreversible deletion has no Undo"


def test_cancel_deletes_nothing(qapp, soccer_week, sheets) -> None:
    sheets.askDeleteBlock("activity-1", -1)
    sheets.answer("stay")
    _settled(qapp, soccer_week)
    kept = _soccer(soccer_week)
    assert kept is not None and not kept.get("missed_days")
    assert sheets.notice == ""


def test_delete_from_one_day_asks_once_names_the_day_and_offers_three_ways(qapp, soccer_week, sheets) -> None:
    session = soccer_week.session
    sheets.askDeleteBlock("activity-1", 1)
    ask = dict(sheets.ask)
    occurrence = date.fromisoformat(date_for_day(session.week_start, 1))
    stamp = f"{occurrence.day} {occurrence.strftime('%b')}"
    assert ask["title"] == "Delete Soccer?"
    assert [(card["id"], card["title"]) for card in ask["cards"]] == [
        ("day", f"Just Tuesday {stamp}"),
        ("week", "This week only"),
        ("every", "This week and every week after"),
    ]
    assert "Earlier weeks keep Soccer." in ask["cards"][2]["line"]
    assert [answer["id"] for answer in ask["answers"]] == ["stay", "day", "week", "every"]
    assert [answer["label"] for answer in ask["answers"]] == [
        "Cancel",
        "This day only",
        "This week only",
        "This week and later",
    ]
    sheets.answer("week")
    _settled(qapp, soccer_week)
    assert _soccer(soccer_week)["missed_days"] == [1, 3]
    assert sheets.notice == "Deleted Soccer from this week." and sheets.noticeUndo is True
    assert sheets.ask == {}, "the week choice did not open a second question"
    sheets.undoNotice()
    _settled(qapp, soccer_week)
    assert not _soccer(soccer_week).get("missed_days")


@pytest.mark.xfail(
    strict=True,
    reason="product gap: saving School hours says 'School now 9:00 AM–3:00 PM every week' through the "
    "Widgets toast (window._set_notice with no button), which Material's screen never shows",
)
def test_new_school_hours_say_every_week_and_offer_no_undo(qapp, shell, sheets) -> None:
    from desktop.tests.settings.support_material_settings import _open_settings, _panel
    from desktop.tests.week.support_material import _snack

    shell.session.preferences = {**(shell.session.preferences or {}), "clock_24h": False}
    _open_settings(qapp, shell, "planning")
    panel = _panel(shell)
    panel.setSchoolStart("9 am")
    panel.setSchoolEnd("3 pm")
    panel.saveSchoolHours()
    wait_until(qapp, lambda: not shell.session.busy and not shell.session.dirty)
    pump(qapp, 10)
    assert _snack(shell) == "School now 9:00 AM–3:00 PM every week"
