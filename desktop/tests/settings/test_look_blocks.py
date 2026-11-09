"""The Blocks look knob: what each block is given and what the calendar paints.

A stylesheet cannot reach a painted block, so this knob is the one most likely to be stored and
ignored. Expected colours come from the palette and the category table, never from a grab of the
current output. Where the blocks are drawn on screen is in the settings pictures.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QApplication, QWidget

from desktop.native.calendar import CATEGORIES
from desktop.native.hours.canvas import Drawn
from desktop.native.hours.classic import ClassicWeek
from desktop.native.hours.hand import Hand, Verdict
from desktop.native.hours.month import MonthGrid
from desktop.native.look import (
    LOOK_DEFAULTS,
    LOOK_KNOBS,
    block_paint,
    pack_stylesheet,
    resolved_palette,
)
from desktop.native.tokens import SINK, family_colours, mix_oklab
from desktop.native.weekmodel import build_week
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.settings.support_look import look_of
from desktop.tests.waiting import wait_until
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


def week(qapp: QApplication, look: dict | None, pack: str = "nocturne") -> tuple[ClassicWeek, dict]:  # noqa: F811
    """Today's app's week, opened at 07:00 so School and Club are both on screen."""
    palette = resolved_palette(pack, pack in {"nocturne", "dark-frost"}, look)
    host = QWidget()
    HOSTS.append(host)
    calendar = ClassicWeek(Hand(lambda block_id, from_day, span: Verdict(False, ""), host))
    calendar.resize(1000, 800)
    calendar.set_look(look, palette)
    calendar.set_week(build_week(WEEK, [SCHOOL, CLUB], {}, None), None, 7 * 60)
    calendar.show()
    qapp.processEvents()
    calendar.hours.relayout()
    qapp.processEvents()
    return calendar, palette


def block_on(calendar: ClassicWeek, block_id: str) -> tuple[Drawn, QRectF]:
    hours = calendar.hours
    return next(
        (drawn, rect)
        for track in hours.tracks
        for drawn, rect in hours.drawn(track)
        if drawn.block_id == block_id
    )


def shape(calendar: ClassicWeek, block_id: str) -> tuple[str, str, str | None, str | None]:
    """Fill, ink, outline and edge, as the week paints the block."""
    fill, ink, outline, edge = calendar.hours.painter.fills(block_on(calendar, block_id)[0])
    return fill.name(), ink.name(), outline and outline.name(), edge and edge.name()


def painted(opened: NativeWindow, block_id: str) -> tuple[str, str | None]:
    hours = opened.week_table.hours
    if not hours.tracks:
        opened.show()
        hours.resize(980, 640)
        hours.relayout()
    track = hours.track_for(0, 8 * 60)
    drawn = next(item for item, _rect in hours.drawn(track) if item.block_id == block_id)
    fill, _ink, _outline, edge = hours.painter.fills(drawn)
    return fill.name(), None if edge is None else edge.name()


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


def test_a_filled_block_is_the_pale_category_colour_with_ink_that_reads(qapp: QApplication) -> None:  # noqa: F811
    calendar, palette = week(qapp, knobs_of(blocks="filled"), pack="slate")
    assert shape(calendar, "school") == (PALE, palette["text"], None, None)
    # No category: the palette's own block colours, not a fixed light grey that glares on a dark pack.
    assert shape(calendar, "club")[:2] == (palette["block_locked"], palette["block_locked_ink"])


def test_a_filled_block_on_a_dark_pack_is_deep_with_light_ink(qapp: QApplication) -> None:  # noqa: F811
    """Pale blue on near-black glared, and its black ink read as a hole in the page. The fill is
    School's tone sunk into the panel, as CSS's color-mix in OKLab makes it, in the look's own ink."""
    calendar, palette = week(qapp, knobs_of(blocks="filled"))
    deep = mix_oklab(TONE, palette["panel"], SINK)
    assert shape(calendar, "school") == (deep, palette["text"], None, None)
    assert shape(calendar, "club")[:2] == (palette["block_locked"], palette["block_locked_ink"])


def test_an_outlined_block_is_drawn_as_one_outline_in_the_strong_colour(qapp: QApplication) -> None:  # noqa: F811
    calendar, palette = week(qapp, knobs_of(blocks="outline"))
    assert shape(calendar, "school")[:3] == (palette["grid"], palette["text"], DEEP_MARK)


def test_an_edge_block_is_its_category_fill_with_the_strong_colour_down_its_left(
    qapp: QApplication,  # noqa: F811
) -> None:
    """Edge, the default since decision 14 of 0.17: the fill a Filled block has, and the mark as a
    3-pixel edge."""
    calendar, palette = week(qapp, look_of("default"))
    deep = mix_oklab(TONE, palette["panel"], SINK)
    fill, _ink, outline, edge = shape(calendar, "school")
    assert (fill, outline, edge) == (deep, None, DEEP_MARK)


def test_the_outline_is_the_strong_colour_on_a_light_pack(qapp: QApplication) -> None:  # noqa: F811
    calendar, palette = week(qapp, knobs_of(blocks="outline"), pack="slate")
    assert shape(calendar, "school")[2] == STRONG
    assert palette["grid"] == "#ffffff"


def test_changing_the_look_repaints_the_week_already_on_screen(qapp: QApplication) -> None:  # noqa: F811
    calendar, palette = week(qapp, knobs_of(blocks="filled"), pack="slate")
    assert shape(calendar, "school")[::3] == (PALE, None)
    calendar.set_look(knobs_of(blocks="edge"), palette)
    fill, _ink, _outline, edge = shape(calendar, "school")
    assert (fill, edge) == (PALE, STRONG)


def test_days_outside_the_month_use_the_palettes_muted_ink(qapp: QApplication) -> None:  # noqa: F811
    day = {"due_ids": [], "session_count": 0, "locked_count": 0, "scheduled_min": 0, "focus_min": 0}
    snapshot = {
        "month": "2026-09",
        "days": [
            {**day, "date": "2026-08-31", "in_month": False},
            {**day, "date": "2026-09-01", "in_month": True},
        ],
        "overdue": [],
    }
    grid = MonthGrid()
    terminal = resolved_palette("slate", False, {"preset": "terminal", "knobs": {}})
    grid.set_month(snapshot, False)
    grid.set_palette(terminal)
    assert grid.canvas.cells[0].in_month is False
    assert grid.canvas.painter.c("muted").name() == terminal["muted"] == "#8b949e"


def test_todays_name_above_the_week_is_marked_and_no_other(qapp: QApplication) -> None:  # noqa: F811
    calendar, _palette = week(qapp, look_of("default"), pack="slate")
    assert [label.property("today") for label in calendar._name_labels] == [False] * 7
    calendar.set_week(build_week(WEEK, [SCHOOL, CLUB], {}, None), 2, 7 * 60)
    assert [label.property("today") for label in calendar._name_labels] == [False, False, True] + [False] * 4


def test_a_look_chosen_in_the_window_reaches_the_calendar_not_only_the_stylesheet(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    window.session.add_block(dict(SCHOOL))
    window.session.save()
    wait_until(qapp, lambda: not window.session.busy and not window.session.dirty)
    assert painted(window, "school") == (PALE, STRONG)

    # What Settings does when the student presses OK.
    window._look = knobs_of(blocks="outlined")
    window._apply_appearance()
    fill, edge = painted(window, "school")
    assert edge is None
    assert fill != PALE
    assert "border: 1px solid" in window.styleSheet()
