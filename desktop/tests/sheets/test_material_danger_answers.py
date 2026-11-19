"""The answers that delete something or cannot be taken back use Material's error colour, in every prompt
and sheet, light and dark, and the ink on them reads like the other Material colours."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QColor

from desktop.native.material.theme import CONTRASTS, ONE_MODE, PRESETS, scheme
from desktop.native.tokens import contrast
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import named, pump
from desktop.tests.sheets.support_prompt_walk import bridge_sheets as sheets_of
from desktop.tests.sheets.support_prompt_walk import (
    footer_buttons,
    looked,
    prompt_item,
    week_with_school,
)
from desktop.tests.sheets.test_prompts_stay_in_their_card import poses
from desktop.tests.window_support import qapp  # noqa: F401

pytestmark = pytest.mark.real_surface

# The prompt and the answer button on it that is the destructive one.
DANGEROUS = {
    "discard": "discard",
    "sign-out": "yes",
    "restore-copy": "restore",
    "delete-account": "delete",
    "replace-week": "replace",
    "replace-focus": "replace",
    "delete-homework": "delete",
    "delete-alarm": "delete",
    "delete-unfinished": "delete",
}


def _colour(item, name: str) -> str:
    return QColor(item.property(name)).name().lower()


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_the_destructive_answer_is_the_error_colour_and_the_others_are_not(qapp, window, mode) -> None:
    week_with_school(qapp, window)
    sheets = sheets_of(window)
    theme = window._material_page.bridge.theme
    problems: list[str] = []
    with looked(window, mode=mode, scale=1.0, size=(1280, 800)):
        theme = window._material_page.bridge.theme
        error, ink = str(theme["error"]).lower(), str(theme["inkError"]).lower()
        for name, pose in poses(window):
            pose()
            pump(qapp, 30)
            prompt = prompt_item(window)
            assert prompt is not None, name
            for button in footer_buttons(prompt):
                button_id = str(button.objectName()).removeprefix("prompt_")
                red = _colour(button, "fill") == error
                if (button_id == DANGEROUS.get(name)) != red:
                    problems.append(f"{name}/{button_id}: red={red}")
                elif red and _colour(button, "ink") != ink:
                    problems.append(f"{name}/{button_id}: ink {_colour(button, 'ink')}")
            sheets.forceClose()
            pump(qapp, 10)
    assert not problems, problems
    assert named(window._material_page.root, "sheetPrompt") is not None


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_a_card_that_cannot_be_undone_turns_delete_red_only_while_it_is_picked(qapp, window, mode) -> None:
    """Jonathan, 2026-11-18: answers that cannot be undone are red. With choice cards the safe card is picked
    first, so Delete is the filled colour; picking This week and later makes Delete red."""
    week_with_school(qapp, window)
    sheets = sheets_of(window)
    with looked(window, mode=mode, scale=1.0, size=(1280, 800)):
        error = str(window._material_page.bridge.theme["error"]).lower()
        sheets.askDeleteBlock("school", 1)
        pump(qapp, 30)
        prompt = prompt_item(window)

        def delete_is_red() -> bool:
            (confirm,) = [b for b in footer_buttons(prompt) if str(b.objectName()) == "prompt_confirm"]
            return _colour(confirm, "fill") == error

        assert not delete_is_red(), "Delete is red while a card you can undo is picked"
        prompt.setProperty("pick", 2)
        pump(qapp, 10)
        assert delete_is_red(), "Delete is not red with This week and later picked"
        sheets.forceClose()
        pump(qapp, 10)


@pytest.mark.parametrize("preset", PRESETS)
@pytest.mark.parametrize("level", CONTRASTS)
def test_the_ink_on_the_error_fill_reads_in_every_look_light_and_dark(preset: str, level: str) -> None:
    floor = 7.0 if preset == "High contrast" else 4.5
    for mode in [ONE_MODE[preset]] if preset in ONE_MODE else ["light", "dark"]:
        colours = scheme(preset, mode, level)
        assert contrast(colours["onError"], colours["error"]) >= floor, (preset, mode, level)
