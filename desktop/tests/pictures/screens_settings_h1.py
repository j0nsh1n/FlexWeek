"""The pictures of the look and its editor: what the code checks of these were pixels, colours and
positions, and are judged on the picture now (spec.md, Testing structure, rule 6)."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native import motion
from desktop.native.look import look_menu_token
from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.settings.support_look_editor import open_editor, pump, type_colour
from desktop.tests.waiting import wait_until

EDITOR_SOURCES = (
    "desktop/native/look_editor.py",
    "desktop/native/look.py",
    "desktop/native/custom_look.py",
    "desktop/native/settings.py",
)
WEEK_SOURCES = ("desktop/native/hours", "desktop/native/look.py")

SCHOOL = {
    "id": "school",
    "title": "School",
    "kind": "locked",
    "category": "class",
    "start": "08:00",
    "duration_min": 405,
    "days": [0],
}
CLUB = {"id": "club", "title": "Club", "kind": "locked", "start": "10:00", "duration_min": 30, "days": [1]}


def _app() -> QApplication:
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    return app


def _editor(window: NativeWindow) -> tuple[object, object]:
    page, editor = open_editor(_app(), window)
    wait_until(_app(), lambda: not motion.busy())
    pump(_app(), 20)
    return page, editor


def _settled(window: NativeWindow) -> None:
    wait_until(_app(), lambda: not window.session.busy and not window.session.dirty)


def _week_with_blocks(window: NativeWindow, blocks: str | None) -> object:
    """The week with School (class colour) and Club (no category) placed, wearing the Blocks knob."""
    for block in (SCHOOL, CLUB):
        window.session.add_block(dict(block))
    window.session.save()
    _settled(window)
    if blocks is not None:
        window._look = {"preset": "default", "knobs": {"blocks": blocks}}
        window._apply_appearance()
    hours = window.week_table.hours
    if not hours.tracks:
        hours.resize(980, 640)
        hours.relayout()
    pump(_app(), 20)
    return None


def _editor_groups_open(window: NativeWindow) -> object:
    _page, editor = _editor(window)
    for card in editor.groups.values():
        card.toggle.setChecked(True)
    type_colour(_app(), editor, "page", "#f0f0f0")
    editor.categories["study"].exact.click()
    pump(_app(), 20)
    return editor


def _editor_started_from_dark(window: NativeWindow) -> object:
    _page, editor = _editor(window)
    editor._start_from("base:dark")
    pump(_app(), 20)
    return editor


def _editor_after_a_page_colour(window: NativeWindow) -> object:
    _page, editor = _editor(window)
    type_colour(_app(), editor, "page", "#1e2430")
    return editor


def _editor_grey_text(window: NativeWindow) -> object:
    _page, editor = _editor(window)
    editor._start_from("base:light")
    pump(_app(), 20)
    type_colour(_app(), editor, "text", "#999999")
    return editor


def _week_under_grey_text(window: NativeWindow) -> object:
    window.session.add_block(dict(SCHOOL))
    window.session.save()
    _settled(window)
    _page, editor = _editor(window)
    editor._start_from("base:light")
    pump(_app(), 20)
    type_colour(_app(), editor, "text", "#999999")
    hours = window.week_table.hours
    if not hours.tracks:
        hours.resize(980, 640)
        hours.relayout()
    return hours


def _editor_changed_chip(window: NativeWindow) -> object:
    _page, editor = _editor(window)
    # A pale typed accent is the case where the plain accent cannot be words on its own tint.
    type_colour(_app(), editor, "accent", "#dfff00")
    type_colour(_app(), editor, "page", "#1e2430")
    return editor


def _poster_in_settings(window: NativeWindow) -> object:
    window._open_settings()
    page = window._settings
    pump(_app(), 20)
    page.look.setCurrentIndex(page.look.findData(look_menu_token("preset", "poster")))
    pump(_app(), 20)
    return page


def _settings_page(window: NativeWindow) -> object:
    window._open_settings()
    pump(_app(), 20)
    return window._settings


def _editor_opened(window: NativeWindow) -> object:
    _page, editor = _editor(window)
    return editor


SCREENS: list[Screen] = [
    Screen(
        id="settings.look_editor",
        area="settings",
        prepare=_editor_opened,
        checks=(
            "the editor fills the whole Settings page; the colour fields (Accent, Page, Card, Text, Line)"
            " all end at the same right edge and the Accent swatch starts where the others' do; Reset "
            "all, Export and Import are outlined like Save as new, with a 1 px edge in the outline colour"
            " that stands out from the button's fill"
        ),
        sources=EDITOR_SOURCES,
        main=True,
    ),
    Screen(
        id="settings.look_editor_groups_open",
        area="settings",
        prepare=_editor_groups_open,
        checks=(
            "with every group open, in Light and in High contrast, nothing is cut at the column's right "
            "edge: the four motion levels, a category row with its switch and a group's name with its tag"
            " each fit the 360 px column, and at High contrast's large text the column widens instead"
        ),
        sources=EDITOR_SOURCES,
        main=True,
    ),
    Screen(
        id="settings.look_editor_dark_start",
        area="settings",
        prepare=_editor_started_from_dark,
        checks=(
            "after Start from Dark the editor's own header is drawn in Dark's page colour, so the editor "
            "wears the look it was started from"
        ),
        sources=EDITOR_SOURCES,
    ),
    Screen(
        id="settings.look_editor_preview",
        area="settings",
        prepare=_editor_after_a_page_colour,
        checks=(
            "after typing the page colour #1e2430 the preview picture shows the whole window at its size "
            "with that colour as its page, not the colour it had when the editor opened"
        ),
        sources=EDITOR_SOURCES,
    ),
    Screen(
        id="settings.look_editor_grey_text",
        area="settings",
        prepare=_editor_grey_text,
        checks=(
            "with grey text (#999999) on Light the Readability lines are fully visible and read in plain "
            "words, the block colours as one line 'Text on 8 block colours is N:1 at worst' with a Fix"
        ),
        sources=EDITOR_SOURCES,
    ),
    Screen(
        id="settings.look_grey_text_on_blocks",
        area="settings",
        prepare=_week_under_grey_text,
        checks=(
            "the week writes the grey text the student chose on its blocks: inside the School block no "
            "black ink stands in (nothing darker than 0x50 in any channel) and the text pixels are the "
            "chosen grey #999999 within 8 per channel"
        ),
        sources=EDITOR_SOURCES + WEEK_SOURCES,
    ),
    Screen(
        id="settings.look_editor_changed_chip",
        area="settings",
        prepare=_editor_changed_chip,
        checks=(
            "the Changed chip's words read at least 4.5 to 1 on their tint, with a pale typed accent "
            "(#dfff00) and in every look: Light, Dark, Paper, Ink, Pastel, Terminal, Poster and High "
            "contrast (where the chip is on the plain panel)"
        ),
        sources=EDITOR_SOURCES,
        main=True,
    ),
    Screen(
        id="settings.look_poster_preview",
        area="settings",
        prepare=_poster_in_settings,
        checks=(
            "Settings, Look with Poster chosen: the preview's column rules are the week's rule colour "
            "(the page's black at 14%, a soft line), not the hairline's solid black; there are more rule-"
            "coloured pixels than hairline-black ones below the title bar"
        ),
        sources=("desktop/native/look_preview.py", "desktop/native/look.py", "desktop/native/settings.py"),
    ),
    Screen(
        id="settings.look_switch_art",
        area="settings",
        prepare=_settings_page,
        checks=(
            "every switch is readable in every pack, preset and light or dark device setting: an off "
            "switch's outline and knob are at least 3 to 1 on the card and on the track (the track is the"
            " card's own colour), and a disabled switch, on or off, keeps its outline and knob at least 3"
            " to 1 on the card and on its track"
        ),
        sources=("desktop/native/widgets.py", "desktop/native/look.py", "desktop/native/settings.py"),
        main=True,
    ),
    Screen(
        id="settings.look_blocks_edge",
        area="settings",
        prepare=lambda window: _week_with_blocks(window, None),
        checks=(
            "Blocks as Edge, the default: School is its category fill with the category's strong colour "
            "as a 3 px edge down its left side and the plain fill inside, past the text"
        ),
        sources=WEEK_SOURCES,
        main=True,
    ),
    Screen(
        id="settings.look_blocks_outline",
        area="settings",
        prepare=lambda window: _week_with_blocks(window, "outline"),
        checks=(
            "Blocks as Outline: School is one 2 px outline in the category's strong colour with the grid "
            "colour inside; on a light look the outline stays visible and does not vanish into a pale "
            "fill"
        ),
        sources=WEEK_SOURCES,
    ),
    Screen(
        id="settings.look_blocks_filled",
        area="settings",
        prepare=lambda window: _week_with_blocks(window, "filled"),
        checks=(
            "Blocks as Filled: School is the whole category fill (pale on a light look, the tone sunk "
            "into the panel on a dark one) with no edge, and its ink reads on it; the Club block with no "
            "category wears the palette's own block colours"
        ),
        sources=WEEK_SOURCES,
    ),
    Screen(
        id="settings.look_today_chip",
        area="settings",
        prepare=lambda window: _week_with_blocks(window, None),
        checks=(
            "above the week only today's date sits in an accent chip (more than 20 accent pixels in its "
            "label) and no other day's date uses the accent"
        ),
        sources=WEEK_SOURCES,
    ),
]
