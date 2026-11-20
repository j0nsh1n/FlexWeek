"""The two multi-answer questions as cards: Delete School? (one day of a Setup block) and Edited weeks.
The safe, undoable choice is picked first; Up and Down move the pick, Enter confirms it, Esc cancels;
the pick is said in the card's accessible name; and each choice does what the old four buttons did."""

# ruff: noqa: F811
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import named, pump, quick_of, visuals
from desktop.tests.sheets.support_prompt_walk import bridge_sheets as sheets_of
from desktop.tests.sheets.support_prompt_walk import prompt_item, week_with_school
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

LINE = "Changing School times also changes 2 other weeks."


def keys(window: NativeWindow, *pressed: Qt.Key) -> None:
    quick = quick_of(window)
    for key in pressed:
        QTest.keyClick(quick, key)
        pump(QApplication.instance(), 20)


def cards_of(prompt) -> list:
    return [item for item in visuals(prompt) if str(item.objectName()).startswith("prompt_card_")]


def picked(prompt) -> list[str]:
    return [
        str(c.objectName()).removeprefix("prompt_card_") for c in cards_of(prompt) if c.property("picked")
    ]


def raise_delete(qapp, window, day: int = 1):
    week_with_school(qapp, window)
    sheets = sheets_of(window)
    sheets.askDeleteBlock("school", day)
    pump(qapp, 30)
    return sheets, prompt_item(window)


def test_delete_one_day_offers_cards_with_the_undoable_choice_picked_first(qapp, window) -> None:
    sheets, prompt = raise_delete(qapp, window)
    assert [card["id"] for card in sheets.ask["cards"]] == ["day", "week", "every"]
    assert sheets.ask["confirm"] == "Delete"
    assert [str(c.objectName()) for c in cards_of(prompt)] == [
        "prompt_card_day",
        "prompt_card_week",
        "prompt_card_every",
    ]
    assert picked(prompt) == ["day"]
    spoken = [str(c.property("spoken")) for c in cards_of(prompt)]
    assert spoken[0].endswith("Picked.") and all(line.endswith("Not picked.") for line in spoken[1:])


def test_a_delete_with_no_day_offers_this_week_first(qapp, window) -> None:
    sheets, prompt = raise_delete(qapp, window, day=-1)
    assert [card["id"] for card in sheets.ask["cards"]] == ["week", "every"]
    assert picked(prompt) == ["week"]


def test_down_and_up_move_the_pick_and_stop_at_the_ends(qapp, window) -> None:
    _sheets, prompt = raise_delete(qapp, window)
    keys(window, Qt.Key.Key_Up)
    assert picked(prompt) == ["day"]
    keys(window, Qt.Key.Key_Down)
    assert picked(prompt) == ["week"]
    keys(window, Qt.Key.Key_Down, Qt.Key.Key_Down)
    assert picked(prompt) == ["every"]
    keys(window, Qt.Key.Key_Up)
    assert picked(prompt) == ["week"]
    assert str([c for c in cards_of(prompt) if c.property("picked")][0].property("spoken")).endswith(
        "Picked."
    )


def test_a_click_on_a_card_picks_it_without_answering(qapp, window) -> None:
    from desktop.tests.sheets.support_material_sheets import click

    sheets, prompt = raise_delete(qapp, window)
    click(window, named(prompt, "prompt_card_every")[0])
    pump(qapp, 20)
    assert picked(prompt) == ["every"]
    assert sheets.ask["id"] == "delete-block"


def days_of_school(window) -> int:
    return sum(len(b.get("days") or []) for b in window.session.blocks if str(b["id"]).startswith("school"))


def test_enter_confirms_the_picked_card_and_the_default_deletes_only_that_day(qapp, window) -> None:
    sheets, _prompt = raise_delete(qapp, window)
    before = days_of_school(window)
    keys(window, Qt.Key.Key_Return)
    assert sheets.ask == {}
    assert days_of_school(window) == before - 1
    assert sheets.noticeUndo is True


def test_enter_after_down_deletes_this_week_only_and_can_be_undone(qapp, window) -> None:
    sheets, _prompt = raise_delete(qapp, window)
    keys(window, Qt.Key.Key_Down, Qt.Key.Key_Return)
    assert sheets.ask == {}
    assert sheets.noticeUndo is True
    assert not [
        b for b in window.session.blocks if str(b["id"]).startswith("school") and not b.get("missed_days")
    ]


def test_every_week_after_can_be_undone_with_what_came_after_it(qapp, window) -> None:
    sheets, prompt = raise_delete(qapp, window)
    assert sheets.ask["cards"][2]["line"].endswith("You can undo this, with anything changed after it.")
    keys(window, Qt.Key.Key_Down, Qt.Key.Key_Down, Qt.Key.Key_Return)
    assert sheets.ask == {}
    wait_until(qapp, lambda: sheets.noticeUndo)
    assert "every week after" in str(sheets.notice)
    assert str(sheets.notice).endswith("Undo also takes back anything changed after it.")


def test_escape_cancels_and_deletes_nothing(qapp, window) -> None:
    sheets, _prompt = raise_delete(qapp, window)
    before = days_of_school(window)
    keys(window, Qt.Key.Key_Down, Qt.Key.Key_Escape)
    assert sheets.ask == {}
    assert days_of_school(window) == before


def test_the_cancel_button_cancels_and_deletes_nothing(qapp, window) -> None:
    from desktop.tests.sheets.support_material_sheets import click

    sheets, prompt = raise_delete(qapp, window)
    before = days_of_school(window)
    click(window, named(prompt, "prompt_stay")[0])
    pump(qapp, 20)
    assert sheets.ask == {}
    assert days_of_school(window) == before


@pytest.mark.parametrize(
    ("presses", "expected"),
    [
        ((), "keep"),
        ((Qt.Key.Key_Down,), "from_today"),
        ((Qt.Key.Key_Down, Qt.Key.Key_Down), "replace"),
    ],
)
def test_edited_weeks_confirms_the_picked_answer(qapp, window, presses, expected) -> None:
    week_with_school(qapp, window)
    sheets = sheets_of(window)
    got: list = []
    sheets.pose_edited(NativeWindow._edited_ask(LINE), got.append)
    pump(qapp, 30)
    prompt = prompt_item(window)
    assert [str(c.objectName()) for c in cards_of(prompt)] == [
        "prompt_card_keep",
        "prompt_card_from_today",
        "prompt_card_replace",
    ]
    assert picked(prompt) == ["keep"]
    keys(window, *presses, Qt.Key.Key_Return)
    assert got == [expected]


def test_edited_weeks_escape_and_cancel_answer_none(qapp, window) -> None:
    week_with_school(qapp, window)
    sheets = sheets_of(window)
    got: list = []
    sheets.pose_edited(NativeWindow._edited_ask(LINE), got.append)
    pump(qapp, 30)
    keys(window, Qt.Key.Key_Down, Qt.Key.Key_Escape)
    assert got == [None]
    sheets.pose_edited(NativeWindow._edited_ask(LINE), got.append)
    pump(qapp, 30)
    from desktop.tests.sheets.support_material_sheets import click

    click(window, named(prompt_item(window), "prompt_stay")[0])
    pump(qapp, 20)
    assert got == [None, None]


def test_the_old_answers_are_still_on_both_questions(qapp, window) -> None:
    week_with_school(qapp, window)
    sheets = sheets_of(window)
    sheets.askDeleteBlock("school", 1)
    assert [a["id"] for a in sheets.ask["answers"]] == ["stay", "day", "week", "every"]
    ask = NativeWindow._edited_ask(LINE)
    assert [a["id"] for a in ask["answers"]] == ["keep", "replace", "from_today", "stay"]
    assert {c["id"] for c in ask["cards"]} == {"keep", "replace", "from_today"}
