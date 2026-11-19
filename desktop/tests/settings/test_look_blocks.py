"""The Blocks look knob: what each block is given and what the calendar paints.

A stylesheet cannot reach a painted block, so this knob is the one most likely to be stored and
ignored. Expected colours come from the palette and the category table, never from a grab of the
current output. Where the blocks are drawn on screen is in the settings pictures.
"""

from __future__ import annotations

from desktop.native.calendar import CATEGORIES
from desktop.native.look import (
    LOOK_DEFAULTS,
    LOOK_KNOBS,
    block_paint,
    pack_stylesheet,
    resolved_palette,
)
from desktop.native.tokens import family_colours
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.settings.support_look import look_of
from desktop.tests.window_support import qapp  # noqa: F401

WEEK = "2026-09-14"
SCHOOL = {
    "id": "school",
    "title": "School",
    "kind": "locked",
    "category": "class",
    "start": "08:00",
    "duration_min": 60,
    "days": [0],
}
CLUB = {"id": "club", "title": "Club", "kind": "locked", "start": "10:00", "duration_min": 30, "days": [1]}
# School's colours: the pale fill and strong mark of a light look, and the tone and mark of a dark one.
SCHOOL_FAMILY = family_colours(250)
PALE, STRONG = SCHOOL_FAMILY["light"]
TONE, DEEP_MARK = SCHOOL_FAMILY["dark"]
# The hosts of the hands these tests make: a hand is its host's Qt child and keeps no reference to it.
HOSTS: list = []


def knobs_of(**knobs: str) -> dict:
    return look_of("default", **knobs)










def test_the_category_table_is_what_these_tests_assume() -> None:
    assert (CATEGORIES["class"]["color"], CATEGORIES["class"]["mark"]) == (PALE, STRONG)
    assert CATEGORIES["class"]["dark"] == (TONE, DEEP_MARK)


def test_every_knob_value_changes_what_is_drawn() -> None:
    """A control that stores a value nothing reads is a quiet click. Three of seven knobs once were."""
    palette = resolved_palette("nocturne", True, None)
    base_sheet = pack_stylesheet("nocturne", True, look_of("default"))
    base_block = block_paint(look_of("default"), palette, "#3b82f6")
    for knob, values in LOOK_KNOBS.items():
        for value in values:
            if value == LOOK_DEFAULTS[knob]:
                continue
            chosen = knobs_of(**{knob: value})
            if knob == "blocks":
                # Calendar blocks are painted per cell, not by the window stylesheet.
                drawn = block_paint(chosen, palette, "#3b82f6")
                assert drawn != base_block, f"blocks={value} draws nothing new"
            else:
                sheet = pack_stylesheet("nocturne", True, chosen)
                assert sheet != base_sheet, f"{knob}={value} draws nothing new"


def test_a_block_shows_its_category_colour_in_the_place_the_knob_names() -> None:
    palette = resolved_palette("nocturne", True, None)
    blue = "#3b82f6"
    filled = block_paint(knobs_of(blocks="filled"), resolved_palette("slate", False, None), blue)
    assert (filled["fill"], filled["outline"], filled["edge"]) == (blue, None, None)
    outlined = block_paint(knobs_of(blocks="outline"), palette, blue)
    assert (outlined["fill"], outlined["outline"], outlined["edge"]) == (palette["grid"], blue, None)
    assert outlined["ink"] == palette["text"]
    # Edge, the default (decision 14 of 0.17): Filled, with the mark down its side.
    edge = block_paint(look_of("default"), palette, blue)
    assert (edge["mode"], edge["fill"], edge["outline"], edge["edge"]) == ("edge", blue, None, blue)
    # No category: a filled block uses the palette's own block colours, flexible work the warm pair.
    plain = block_paint(look_of("default"), palette, None, "flexible")
    assert (plain["fill"], plain["ink"]) == (palette["block_flex"], palette["block_flex_ink"])
    bare = block_paint(knobs_of(blocks="outline"), palette, None)
    assert bare["outline"] == palette["block_edge"]
    # A pale fill makes a vanishing outline on a light pack, so an outline or an edge uses the strong mark.
    pale, strong = "#bfdbfe", "#3b82f6"
    light = resolved_palette("slate", False, None)
    assert block_paint(look_of("default"), light, pale, "locked", strong)["fill"] == pale
    outlined_pale = block_paint(knobs_of(blocks="outline"), palette, pale, "locked", strong)
    assert outlined_pale["outline"] == strong
    assert block_paint(knobs_of(blocks="edge"), palette, pale, "locked", strong)["edge"] == strong
