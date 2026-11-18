"""The pictures of how a look draws the week's blocks: what the code checks of these were pixels, colours
and positions, and are judged on the picture now (spec.md, Testing structure, rule 6)."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.material_support import pump
from desktop.tests.pictures.screen import Screen
from desktop.tests.waiting import wait_until

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


SCREENS: list[Screen] = [
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
