"""The look editor's model, without Qt: where a setting sits in a custom look, what a draft says about
itself, how the readability rows are worded, and how a typed colour is read."""

from __future__ import annotations

from desktop.native.custom_look import Problem, save_look
from desktop.native.look_editor import (
    START_NOTE,
    Draft,
    hex_colour,
    open_draft,
    problem_rows,
    setting,
    with_setting,
)


def test_a_setting_is_read_and_set_where_it_sits_in_a_custom_look() -> None:
    look = {"name": "Mine", "base": "light", "colours": {"page": "#101010"}}
    assert setting(look, ("colours", "page")) == "#101010"
    assert setting(look, ("colours", "card")) is None and setting(look, ("corners",)) is None
    changed = with_setting(look, ("categories", "class"), {"hue": 140})
    assert changed["categories"] == {"class": {"hue": 140}} and "categories" not in look
    # Back to the base's own: the setting goes, and a set left empty goes with it.
    assert with_setting(look, ("colours", "page"), None) == {"name": "Mine", "base": "light"}
    assert with_setting(changed, ("corners",), 4)["corners"] == 4


def test_the_editor_opens_on_the_look_worn_with_what_is_still_to_save() -> None:
    plain = open_draft("light-frost", {"preset": "default", "knobs": {}}, "default", [])
    assert plain.look["base"] == "light" and not plain.changed() and plain.state() == ""
    night = {"name": "Night study", "base": "nocturne", "corners": 4}
    saved = save_look([], night, "Night study")
    kept = open_draft("system", {"custom": dict(night)}, "default", saved)
    assert kept.saved_as == "Night study" and kept.state() == "Saved"
    moved = open_draft("system", {"custom": {**night, "corners": 12}}, "default", saved)
    assert moved.saved_as == "Night study" and moved.changed() and moved.state() == "Changed, not saved"
    assert moved.changed((("corners",),)) and not moved.changed((("spacing",),))
    # A look kept without saving has every change still to save, against the look it starts from.
    worn = {"custom": {"name": "Mine", "base": "paper", "accent": "sea"}}
    loose = open_draft("system", worn, "default", [])
    assert loose.saved_as is None and loose.start == {"name": "Mine", "base": "paper"} and loose.changed()


def test_a_draft_with_nothing_changed_from_a_saved_look_says_saved() -> None:
    look = {"name": "Mine", "base": "ink"}
    assert Draft(look, dict(look), "Mine").state() == "Saved"
    assert Draft({**look, "corners": 2}, dict(look), "Mine").state() == "Changed, not saved"


def test_three_block_colours_or_more_are_one_line_whose_fix_fixes_them_all() -> None:
    def problem(words: str, ratio: float, field: tuple[str, ...]) -> Problem:
        return Problem(words, "#000000", "#777777", ratio, field, "#aaaaaa")

    text = problem("Text on the page", 3.04, ("colours", "text"))
    blocks = [
        problem(f"Text on {key} blocks", ratio, ("categories", key))
        for key, ratio in (("class", 4.49), ("study", 2.26), ("meals", 3.9))
    ]
    rows = problem_rows([text, *blocks])
    assert [row.words for row in rows] == [
        "Text on the page is 3.0:1",
        "Text on 3 block colours is 2.2:1 at worst",
    ]
    assert rows[1].fixes == tuple(blocks)
    assert [row.words for row in problem_rows([text, *blocks[:2]])] == [
        "Text on the page is 3.0:1",
        "Text on class blocks is 4.4:1",
        "Text on study blocks is 2.2:1",
    ], "two block colours are two lines, and 4.49 never reads as 4.5"


def test_a_colour_is_typed_as_a_hex_code_with_or_without_its_hash() -> None:
    assert hex_colour("#3D6FC4") == "#3d6fc4"
    assert hex_colour(" 3d6fc4 ") == "#3d6fc4"
    assert hex_colour("#36c") == "#3366cc"
    assert [hex_colour(text) for text in ("#3d6fc", "blue", "#3d6fc44", "")] == [None] * 4


def test_the_start_note_says_unsaved_changes_will_be_lost() -> None:
    """T-W23: "What you have not saved is left behind" did not say lost, and "Pick" is a retired word."""
    assert START_NOTE == "Choose a look to start from. Changes you haven't saved will be lost."
