"""A look of the student's own is checked for readability: each pair under 4.5 to 1 is named in plain
English, its Fix moves the colour the student chose until it reads, and Fix all leaves nothing failing."""

from __future__ import annotations

import re

import pytest

from desktop.native import look_editor
from desktop.native.calendar import CATEGORIES
from desktop.native.custom_look import apply_fix, readability
from desktop.native.look import (
    AA_TEXT,
    LOOK_BASES,
    block_paint,
    category_paint,
    contrast,
    pack_stylesheet,
    resolved_palette,
)
from desktop.native.look_editor import fix_all, problem_rows
from desktop.native.tokens import oklch_of

LIME = {"name": "Lime", "base": "light", "accent": "#dfff00"}
GREY_AND_LIME = {**LIME, "colours": {"text": "#9aa0a6", "muted": "#c0c4c8"}}
PALE = ["#dfff00", "#f5d76e", "#ffd1dc", "#bff3ff", "#98ff98", "#00ffff", "#ffff99"]


def worn(custom: dict) -> dict:
    return {"preset": "default", "knobs": {}, "custom": custom}


def sentences(custom: dict) -> list[str]:
    return [row.words for row in problem_rows(readability(custom))]


def fixed_until_it_reads(custom: dict) -> dict:
    for _round in range(5):
        problems = readability(custom)
        if not problems:
            return custom
        custom = apply_fix(custom, problems[0])
    return custom


def link_colours(css: str) -> list[str]:
    names = ("planReviewDetails", "planReviewReplan", "updateSkip", "authSwitch", "authWhy")
    found = []
    for name in names:
        match = re.search(rf"QPushButton#{name}[^{{]*\{{[^}}]*?[; ]color: (#[0-9a-f]{{6}})", css)
        if match:
            found.append(match.group(1))
    return found


def test_each_unreadable_pair_is_named_with_a_fix_that_ends_at_four_and_a_half_to_one() -> None:
    custom = {
        "base": "light",
        "colours": {"page": "#f2f2f2", "card": "#ffffff", "text": "#9a9a9a"},
        "categories": {"class": {"colour": "#5a5a5a"}},
    }
    problems = readability(custom)
    said = {problem.words for problem in problems}
    assert {"Text on the page", "Text on cards", "Muted text on the page", "Muted text on cards"} <= said
    for problem in problems:
        assert problem.ratio < AA_TEXT
        mended = apply_fix(custom, problem)
        palette = resolved_palette("system", False, worn(mended))
        if problem.field[0] == "colours":
            # Moved to read on the page, the cards and the calendar at once.
            key = problem.field[1]
            for ground in ("window", "panel", "grid"):
                assert contrast(palette[key], palette[ground]) >= AA_TEXT, problem
        if problem.field == ("colours", "text"):
            # Its lightness moved; its hue and chroma, what makes it the student's colour, stayed.
            assert oklch_of(palette["text"])[0] < oklch_of("#9a9a9a")[0]
    # Muted text can be set too, and its fix moves it and not the text.
    quiet = {"base": "light", "colours": {"muted": "#c0c0c0"}}
    problem = next((p for p in readability(quiet) if p.words == "Muted text on cards"), None)
    assert problem is not None, "a muted colour set on its own is not checked for reading"
    assert problem.field == ("colours", "muted")
    assert resolved_palette("system", False, worn(apply_fix(quiet, problem)))["text"] == "#111827"
    ended = fixed_until_it_reads(custom)
    assert readability(ended) == []


def test_a_block_colour_that_does_not_read_is_moved_until_its_words_do() -> None:
    """A look of the student's own writes its text on every block, as the mock-up does, so a colour
    the text does not read on is drawn as it is and named with a Fix, not hidden under black or white
    ink. The Fix moves the colour the student chose until the words read."""
    custom = {"base": "dark", "colours": {"text": "#d0d4da"}, "categories": {"study": {"colour": "#8a6fd0"}}}
    palette = resolved_palette("system", True, worn(custom))
    fill, mark = category_paint("study", palette)
    assert block_paint(worn(custom), palette, fill, CATEGORIES["study"]["kind"], mark)["ink"] == "#d0d4da"
    problem = next(p for p in readability(custom, True) if p.field == ("categories", "study"))
    assert problem.ratio < AA_TEXT and problem.words == "Text on Study blocks"
    assert (problem.ink, problem.ground) == ("#d0d4da", "#8a6fd0")
    mended = apply_fix(custom, problem)
    assert mended["categories"]["study"] == {"colour": problem.fixed}
    palette = resolved_palette("system", True, worn(mended))
    assert contrast(palette["text"], category_paint("study", palette)[0]) >= AA_TEXT
    assert abs(oklch_of(problem.fixed)[2] - oklch_of("#8a6fd0")[2]) < 3
    for hue in range(0, 360, 15):
        # A hue on the family reads by construction, in every look.
        for base in LOOK_BASES:
            problems = readability({"base": base, "categories": {"class": {"hue": hue}}})
            assert [p for p in problems if p.field[0] == "categories"] == [], (base, hue)


def test_grey_text_names_every_block_colour_and_its_fix_reads_on_the_blocks_too() -> None:
    """The mock-up's bad colours: grey text on Light fails 4.5 to 1 on every category colour. The Text
    Fix moves the text until it reads on the page, the cards, the calendar and those blocks at once, so
    the categories keep their colours; moved against the surfaces alone, it left every block to fix."""
    grey = {"base": "light", "colours": {"text": "#999999"}}
    blocks = [p for p in readability(grey) if p.field[0] == "categories"]
    assert [p.field[1] for p in blocks] == list(CATEGORIES)
    assert {p.ink for p in blocks} == {"#999999"}
    assert all(p.ratio < AA_TEXT for p in blocks)
    text = next(p for p in readability(grey) if p.field == ("colours", "text"))
    mended = apply_fix(grey, text)
    remaining = readability(mended)
    assert all(problem.field == ("accent",) for problem in remaining)
    assert "categories" not in mended
    # A block on the other side of mid-grey from the page cannot share one text with it: that block
    # keeps its own Fix, and the text still reads on the page and the cards.
    dark_study = {**grey, "categories": {"study": {"colour": "#2a1f5c"}}}
    text = next(p for p in readability(dark_study) if p.field == ("colours", "text"))
    left = readability(apply_fix(dark_study, text))
    assert [p.field for p in left if p.field != ("accent",)] == [("categories", "study")]


def test_the_plan_buttons_warning_reads_in_plain_english() -> None:
    said = sentences(LIME)
    plan = next(words for words in said if "Plan" in words)
    assert re.fullmatch(r"The Plan button's words are \d\.\d:1", plan), plan
    # A singular subject keeps "is".
    assert any(re.fullmatch(r"Today's day name is \d\.\d:1", words) for words in said), said


def test_a_text_colour_warning_still_says_is() -> None:
    assert any(re.fullmatch(r"Text on the page is \d\.\d:1", words) for words in sentences(GREY_AND_LIME))


def test_every_warning_row_is_a_sentence_with_a_verb_and_a_ratio() -> None:
    for words in sentences(GREY_AND_LIME):
        assert re.search(r" (is|are) \d\.\d:1", words), words


@pytest.mark.parametrize("custom", [LIME, GREY_AND_LIME], ids=["lime", "grey text and lime"])
def test_one_rows_fix_leaves_no_row_of_the_same_colour_failing(custom: dict) -> None:
    for row in problem_rows(readability(custom)):
        fixed = custom
        for problem in row.fixes:
            fixed = apply_fix(fixed, problem)
        fields = {problem.field for problem in row.fixes}
        left = [problem for problem in readability(fixed) if problem.field in fields]
        assert not left, (row.words, [(problem.words, problem.ratio) for problem in left])


def test_fix_all_fixes_every_problem_not_only_the_first(monkeypatch: pytest.MonkeyPatch) -> None:
    custom = GREY_AND_LIME
    assert len({problem.field for problem in readability(custom)}) > 4
    # Two rounds are enough only if each round fixes every problem, not one of them.
    monkeypatch.setattr(look_editor, "FIX_ALL_ROUNDS", 2)
    assert readability(fix_all(custom, False)) == []


def test_fix_all_leaves_a_look_that_reads_in_the_dark_too() -> None:
    dark = {"name": "D", "base": "dark", "colours": {"text": "#3a3f47", "muted": "#2a2f36"}}
    assert len(readability(dark, True)) > 1
    assert readability(fix_all(dark, True), True) == []


@pytest.mark.parametrize("accent", PALE)
def test_a_fix_changes_lightness_only_and_keeps_the_hue(accent: str) -> None:
    custom = {"name": "P", "base": "light", "accent": accent}
    light, chroma, hue = oklch_of(accent)
    for problem in readability(custom):
        if problem.field != ("accent",):
            continue
        new_light, new_chroma, new_hue = oklch_of(problem.fixed)
        gap = abs(hue - new_hue)
        assert min(gap, 360 - gap) <= 12, (accent, problem.fixed)
        assert new_chroma >= min(chroma, 0.04) * 0.9, (accent, problem.fixed, "went grey")
        assert new_light < light, (accent, "a pale accent is darkened")


def test_words_in_a_pale_typed_accent_are_drawn_darkened_while_the_warning_stands() -> None:
    look = {"custom": LIME}
    palette = resolved_palette("system", False, look)
    assert palette["accent"] == "#dfff00", "a typed accent stays as typed"
    assert readability(LIME)
    colours = link_colours(pack_stylesheet("system", False, look, "default", palette))
    assert len(colours) >= 4, colours
    for colour in colours:
        for ground in ("window", "panel", "grid"):
            assert contrast(colour, palette[ground]) >= 4.5, (colour, ground)


def test_an_accent_that_already_reads_is_not_moved() -> None:
    palette = resolved_palette("system", False, None)
    colours = link_colours(pack_stylesheet("system", False, None, "default", palette))
    assert colours and set(colours) == {palette["accent"]}, colours
