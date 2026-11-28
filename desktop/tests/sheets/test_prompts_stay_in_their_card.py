"""No Material prompt has a button outside its card. Every prompt the app can raise is put up on a real
window, at Normal and Large text, at 1280x800 and 1024x640, and each footer button must sit wholly inside
the dialog's card. A prompt added without joining this walk fails the last test."""

# ruff: noqa: F811
from __future__ import annotations

import re
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from desktop.native.material import bridge_info, bridge_manage, bridge_sheets
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import named, pump, visuals
from desktop.tests.settings.support_material_settings import _open_settings, _panel
from desktop.tests.sheets.support_prompt_walk import (
    SCALES,
    buttons_outside_card,
    card_of,
    footer_buttons,
    looked,
    prompt_item,
    rect_in_scene,
    week_with_school,
)
from desktop.tests.sheets.support_prompt_walk import (
    bridge_sheets as sheets_of,
)
from desktop.tests.window_support import qapp  # noqa: F401

SIZES = [(1280, 800), (1024, 640)]
EDITED_LINE = "Changing School times also changes 2 other weeks. Your edits to the week of 16 Nov would stay."
NATIVE = Path(bridge_sheets.__file__).resolve().parents[1]

#: Every prompt id the sheet prompts can raise; the guard below compares this with the code.
WALKED = {
    "discard",
    "sign-out",
    "restore-copy",
    "delete-account",
    "import-account",
    "replace-week",
    "delete-block",
    "delete-homework",
    "delete-alarm",
    "delete-unfinished",
    "edited-weeks",
    "before-planning",
    "replace-focus",
    "recovery-file",
    "block-save",
    "doubled-weeks",
}


#: The shape that overflowed in 1.4.0: four plain answers. No prompt asks it now; the frame must hold it.
FOUR_ANSWERS = {
    "id": "four-answers",
    "title": "Delete School?",
    "body": "Delete School on Tuesday 3 Nov only?",
    "answers": [
        {"id": "stay", "label": "Cancel", "kind": "text"},
        {"id": "day", "label": "This day only", "kind": "tonal"},
        {"id": "week", "label": "This week only", "kind": "tonal"},
        {"id": "every", "label": "This week and later", "kind": "filled"},
    ],
}


def alarm_question() -> dict:
    """What removeAlarm asks; the alarm editor needs a stored alarm to get here, so the words are repeated."""
    return {
        "id": "delete-alarm",
        "title": "Delete alarm",
        "body": "Delete Wake up? It will not ring again.",
        "answers": [
            {"id": "stay", "label": "Cancel", "kind": "text"},
            {"id": "delete", "label": "Delete", "kind": "danger"},
        ],
    }


def block_save(window: NativeWindow, put) -> None:
    """What a change to a weekly fixed time asks, with a long name."""
    from desktop.native.material.sheet_block import BlockDraft

    name = "Guitar lesson with the long name of a teacher"
    school = next(item for item in window.session.blocks if item["id"] == "school")
    draft = BlockDraft(window.session, {**school, "title": name})
    put(draft.save_question())()


def doubled_question() -> dict:
    """What a save that doubles a hand-made copy shows: three weeks named and a count of the rest."""
    from datetime import date

    weeks = ["2026-11-16", "2026-11-23", "2026-11-30", "2026-12-07", "2026-12-14"]
    return {
        "id": "doubled-weeks",
        "title": "Guitar is already in later weeks",
        "body": bridge_sheets.doubled_words("Guitar", weeks, date(2026, 11, 5)),
        "answers": [{"id": "ok", "label": "OK", "kind": "tonal"}],
    }


def poses(window: NativeWindow) -> list[tuple[str, object]]:
    sheets = sheets_of(window)

    def put(ask: dict):
        def go() -> None:
            sheets._ask = dict(ask)
            sheets._publish()

        return go

    storage = {"mode": "local"}
    return [
        ("discard", put(bridge_sheets.DISCARD)),
        ("sign-out", put(bridge_info.SIGN_OUT)),
        ("restore-copy", put(bridge_manage.RESTORE_QUESTION)),
        ("delete-account", put(bridge_manage.delete_question("a-long-student-name", storage))),
        ("import-account", put(bridge_manage.import_question({"source_username": "someone-else"}))),
        ("replace-week", put(bridge_manage.replace_week_question("2026-11-02"))),
        ("delete-block", lambda: sheets.askDeleteBlock("school", 1)),
        ("delete-block-week", lambda: sheets.askDeleteBlock("school", -1)),
        ("delete-homework", lambda: sheets.askDeleteHomework("essay")),
        ("delete-alarm", put(alarm_question())),
        ("delete-unfinished", lambda: sheets.askDeleteUnfinished("essay")),
        ("before-planning", put(NativeWindow.before_planning_question("2 overdue, 1 left from last week"))),
        ("replace-focus", put(NativeWindow.replace_focus_question("Biology reading", "Chemistry worksheet"))),
        ("recovery-file", put(NativeWindow.recovery_file_question())),
        ("block-save", lambda: block_save(window, put)),
        ("doubled-weeks", put(doubled_question())),
        ("four-plain-answers", put(FOUR_ANSWERS)),
        ("edited-weeks", lambda: sheets.pose_edited(NativeWindow._edited_ask(EDITED_LINE), lambda _a: None)),
    ]


@pytest.mark.parametrize("size", SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
@pytest.mark.parametrize("scale", list(SCALES), ids=list(SCALES))
def test_no_sheet_prompt_has_a_button_outside_its_card(
    qapp: QApplication, window: NativeWindow, size: tuple[int, int], scale: str
) -> None:
    week_with_school(qapp, window)
    sheets = sheets_of(window)
    problems: list[str] = []
    with looked(window, mode="light", scale=SCALES[scale], size=size):
        for name, pose in poses(window):
            pose()
            pump(qapp, 30)
            prompt = prompt_item(window)
            assert prompt is not None, f"{name} did not come up"
            assert footer_buttons(prompt), f"{name} has no buttons"
            outside = buttons_outside_card(prompt)
            if outside:
                problems.append(f"{name}: {outside}")
            sheets.forceClose()
            pump(qapp, 10)
    assert not problems, f"buttons outside their card at {size} {scale}: {problems}"


def test_title_body_and_cards_of_every_prompt_start_on_one_left_inset(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The title sat 4 px left of the body and the cards: the body made room for a field's focus ring."""
    week_with_school(qapp, window)
    sheets = sheets_of(window)
    problems: list[str] = []
    with looked(window, mode="light", scale=SCALES["Normal"], size=(1280, 800)):
        for name, pose in poses(window):
            pose()
            pump(qapp, 30)
            prompt = prompt_item(window)
            assert prompt is not None, f"{name} did not come up"
            card_left = card_of(prompt).mapToScene(QPointF(0, 0)).x()
            lefts = {"title": named(prompt, "sheetTitle")[0].mapToScene(QPointF(0, 0)).x()}
            body = str(sheets.property("ask").get("body") or "")
            for item in visuals(prompt):
                if body and str(item.property("text") or "") == body:
                    lefts["body"] = item.mapToScene(QPointF(0, 0)).x()
            for cards in named(prompt, "promptCards"):
                if cards.property("visible"):
                    lefts["cards"] = cards.mapToScene(QPointF(0, 0)).x()
            if any(abs(left - (card_left + 24)) > 0.5 for left in lefts.values()):
                problems.append(f"{name}: card left {card_left}, {lefts}")
            sheets.forceClose()
            pump(qapp, 10)
    assert not problems, problems


@pytest.mark.parametrize("size", SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
@pytest.mark.parametrize("scale", list(SCALES), ids=list(SCALES))
def test_no_settings_prompt_has_a_button_outside_its_card(
    qapp: QApplication, window: NativeWindow, size: tuple[int, int], scale: str
) -> None:
    _open_settings(qapp, window)
    problems: list[str] = []
    with looked(window, mode="light", scale=SCALES[scale], size=size):
        _panel(window).openAdvanced()
        pump(qapp, 20)
        root = window._material_page.root
        for name in ("presetPrompt", "importPrompt", "savePrompt", "exportPrompt"):
            prompt = named(root, name)[0]
            prompt.setProperty("open", True)
            pump(qapp, 30)
            card = rect_in_scene(named(prompt, "promptCard")[0])
            buttons = [
                item
                for item in visuals(prompt)
                if str(item.objectName()).startswith("prompt_") and item.property("visible")
            ]
            assert buttons, f"{name} has no buttons"
            for item in buttons:
                box = rect_in_scene(item)
                if (
                    box.left() < card.left() - 0.5
                    or box.right() > card.right() + 0.5
                    or box.bottom() > card.bottom() + 0.5
                ):
                    problems.append(f"{name}: {item.objectName()}")
            prompt.setProperty("open", False)
            pump(qapp, 10)
    assert not problems, f"buttons outside their card at {size} {scale}: {problems}"


def test_every_prompt_the_code_can_raise_is_in_the_walk() -> None:
    found: set[str] = set()
    views = NATIVE.parents[1] / "engine" / "app" / "src" / "views"
    # A prompt moved into any Rust view still has to join the same real-window walk.
    for path in [*(NATIVE / "material").glob("*.py"), NATIVE / "window.py", *views.glob("*.rs")]:
        found |= set(re.findall(r'"id": "([a-z-]+)",\s*"title"', path.read_text()))
    found = {item for item in found if "-" in item or item == "discard"}
    assert found == WALKED, (
        f"prompts missing from the walk: {found - WALKED}; not in the code: {WALKED - found}"
    )
