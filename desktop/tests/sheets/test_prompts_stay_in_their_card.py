"""No Material prompt has a button outside its card. Every prompt the app can raise is put up on a real
window, at Normal and Large text, at 1280x800 and 1024x640, and each footer button must sit wholly inside
the dialog's card. A prompt added without joining this walk fails the last test."""

# ruff: noqa: F811
from __future__ import annotations

import re
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native.material import bridge_info, bridge_manage, bridge_sheets
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import named, pump, visuals
from desktop.tests.settings.support_material_settings import _open_settings, _panel
from desktop.tests.sheets.support_prompt_walk import (
    SCALES,
    buttons_outside_card,
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
            {"id": "delete", "label": "Delete", "kind": "filled"},
        ],
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
    for path in [*(NATIVE / "material").glob("*.py"), NATIVE / "window.py"]:
        found |= set(re.findall(r'"id": "([a-z-]+)",\s*"title"', path.read_text()))
    found = {item for item in found if "-" in item or item == "discard"}
    assert found == WALKED, (
        f"prompts missing from the walk: {found - WALKED}; not in the code: {WALKED - found}"
    )
