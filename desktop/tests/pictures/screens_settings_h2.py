"""Settings pictures: the looks and their colours, the controls, the toast and menus, the style preview's
place on the Look page, and the audit screens (R3.4 forms lane, chunk H2). The checks are what the old
code tests asserted about colours, contrast, positions and sizes, with their numbers."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from desktop.native.weekmodel import Occurrence, WeekModel
from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.settings import support_pictures as pictures
from desktop.tests.window_support import still

LOOK_SOURCES = (
    "desktop/native/look.py",
    "desktop/native/tokens.py",
    "desktop/native/calendar.py",
    "desktop/native/hours",
    "desktop/native/settings.py",
    "desktop/native/style_preview.py",
    "desktop/native/previews.py",
)

# What the old token tests measured for every look, shown on the Look page's preview week.
EVERY_LOOK = (
    "Text reads at 4.5 to 1 (7 to 1 in High contrast) on its ground: the text on the page, cards, fields and "
    "grid; the muted words on the page and cards; error words on the page and cards; the accent's own words "
    "(today's name, the side panel's headings, links) on the page and cards; locked and flexible "
    "block words; "
    "and every category block's words on its fill. "
    "Every category fill sits at one lightness: within 0.02 (OKLab) of the others, Sleep apart. "
    "Homework's mark is at least 20 (OKLab times 100) from every other category's mark after a deuteranope's "
    "colour-blindness simulation, so homework and sports are told apart. "
    "The Now line and the selection reach 3 to 1 over every category block in each block style. "
    "A category icon is its category's mark, only as light or dark as 4.5 to 1 on its own block "
    "takes, in each "
    "block style; free time has no icon; the School icon is not cut off and its 3 px edge keeps the "
    "category's "
    "colour. A one-hour homework block keeps its 16 px book icon inside the block with its padding "
    "(INNER_PAD) "
    "on every side, at Normal and Large text. "
    "The accent never fills a page, card or wash. "
    "In the dark looks (Dark, Nocturne, Ink, Terminal) the rail's homework red reaches 3 to 1 on the page, "
    "cards and fields."
)
EXTRA = {
    "Slate": "",
    "Nocturne": "",
    "High contrast": (
        " The Today's app picture's top band (the day names) is the look's own dark page, lightness under "
        "0.15, not a pale row over a black week. The High contrast look card's title stays on one line at "
        "Normal and Large text. Every choice in Settings is in the text colour on the page and the chosen "
        "one is filled with the accent (#ffd400) in its ink."
    ),
    "Paper": (
        " The card edge is the warm 1 px hairline (#8f877a) and reaches 3 to 1 on the page, the card and "
        "the second card shade. There are no shadows."
    ),
    "Ink": " The card edge is the warm 1 px hairline (#706c65) and reaches 3 to 1 on the page and the card.",
    "Terminal": "",
    "Poster": "",
    "Pastel": " Cards are tinted, not white, and corners are rounder than the default look's.",
}


def look_screen(name: str, main: bool = False) -> Screen:
    slug = name.lower().replace(" ", "_")

    def prepare(window: NativeWindow) -> object:
        pictures.wear(window, name)
        return pictures.settings_at(window, 0)

    return Screen(
        id=f"settings.look_{slug}",
        area="settings",
        prepare=prepare,
        checks=f"The Look page wearing {name}. " + EVERY_LOOK + EXTRA[name],
        sources=LOOK_SOURCES,
        main=main,
        styles=("widgets",),
    )


def top_bar_choice(window: NativeWindow) -> object:
    window.show()
    still(window)
    return window.findChild(QWidget, "segments")


def controls(window: NativeWindow) -> object:
    return pictures.controls_sample(window)


def dropdown(window: NativeWindow) -> object:
    return pictures.dropdown_list(window)


def toast(window: NativeWindow) -> object:
    return pictures.toast_with_undo(window)


def menu(window: NativeWindow) -> object:
    return pictures.open_menu(window)


def next_card_in_terminal(window: NativeWindow) -> object:
    from PySide6.QtWidgets import QVBoxLayout

    from desktop.native.hours.rail import RAIL_PX, NextCard
    from desktop.native.weekmodel import build_week

    pictures.wear(window, "Terminal")
    host = QWidget(window)
    card = NextCard(host)
    QVBoxLayout(host).addWidget(card)
    host.setGeometry(20, 20, RAIL_PX, 300)
    school = {
        "id": "school",
        "title": "School",
        "kind": "locked",
        "category": "class",
        "start": "08:00",
        "duration_min": 405,
        "days": [1],
    }
    card.show_next(build_week("2026-09-28", [school], [], None), 1, 620)
    host.raise_()
    host.show()
    still(host)
    return host


def look_preview(row: int, size: tuple[int, int], *, large: bool = False, motion_off: bool = False):
    def prepare(window: NativeWindow) -> object:
        page = pictures.settings_at(window, row, size)
        if large:
            pictures.wear_large_text(page)
        if motion_off:
            page.motion.setCurrentIndex(page.motion.findData("off"))
            page.motion_level = "off"
            pictures.pump(lambda: False)
        return page

    return prepare


def look_preview_scrolled(window: NativeWindow) -> object:
    page = pictures.settings_at(window, 0, (1400, 900))
    area = page.stack.currentWidget()
    area.verticalScrollBar().setValue(area.verticalScrollBar().maximum())
    pictures.pump(lambda: False)
    return page


def unfinished_panel(window: NativeWindow) -> object:
    from desktop.native.widgets import UnfinishedPanel

    panel = UnfinishedPanel(window)
    panel.setGeometry(20, 20, 320, 400)
    panel.raise_()
    panel.show()
    still(panel)
    return panel


def timeline_fold(window: NativeWindow) -> object:
    from desktop.native.layouts.base import Scene
    from desktop.native.layouts.registry import tokens_for
    from desktop.native.layouts.timeline import TimelineView
    from desktop.native.look import PRESET_PALETTES

    view = TimelineView(window)
    view.setGeometry(0, 0, 1280, 800)
    tokens = tokens_for("timeline", "paper", PRESET_PALETTES["timeline-paper"])
    view.show_week(Scene(WeekModel("2026-10-12", ()), 2, 900, {"fold": "3"}, tokens, 1.0))
    view.raise_()
    view.show()
    still(view)
    return view


def mission_school(window: NativeWindow) -> object:
    from desktop.native.layouts.base import Scene
    from desktop.native.layouts.mission import MissionView
    from desktop.native.layouts.registry import tokens_for
    from desktop.native.look import PRESET_PALETTES

    view = MissionView(window)
    view.setGeometry(0, 0, 1280, 800)
    school = Occurrence("school", "School", "class", 0, 480, 870, False, False, False, None, None, None)
    tokens = tokens_for("mission", "flight-deck", PRESET_PALETTES["flight-deck"])
    view.show_week(Scene(WeekModel("2026-10-12", (school,)), 0, 900, {}, tokens, 1.0))
    view.raise_()
    view.show()
    still(view)
    return view


def week_list_drawer(window: NativeWindow) -> object:
    window.resize(1280, 800)
    window.show()
    window._toggle_week_access_list()
    pictures.pump(lambda: window.week_list_panel.isVisible())
    still(window)
    return window


def material_tokens(window: NativeWindow) -> object:
    window.show()
    still(window)
    return None


SCREENS: list[Screen] = [
    *(
        look_screen(name, main=name in {"Paper", "High contrast"})
        for name in ("Slate", "Nocturne", "High contrast", "Paper", "Ink", "Terminal", "Poster", "Pastel")
    ),
    Screen(
        id="settings.top_bar_choice",
        area="settings",
        prepare=top_bar_choice,
        checks=(
            "The Day / Week / Month choice in the top bar. In a dark look the chosen segment's chip "
            "is lighter "
            "than the track by at least 0.05 (OKLab) and has a 1 px solid ring in #7fa8ff. In High contrast "
            "every segment is in the text colour on the page and the chosen one is filled with the accent "
            "(#ffd400) in its ink; yellow on grey could not be read."
        ),
        sources=("desktop/native/widgets.py", "desktop/native/look.py"),
        main=True,
        styles=("widgets",),
    ),
    Screen(
        id="settings.controls",
        area="settings",
        prepare=controls,
        checks=(
            "Every control takes the look's colours and none disappears on a dark palette. An "
            "unticked box and "
            "an unselected radio button show a clear edge (at least 20 pixels well off the page). A "
            "ticked box "
            "is filled with the accent. A spin box shows its arrows in the muted ink. A switch shows "
            "every line "
            "of its words, at Normal and Large text; its tall form is not cut off at the foot. Settings' "
            "two- and three-way choice and the top bar's choice read every option in the text colour "
            "with the "
            "chosen one filled with the accent. An action button (Check for updates) has an edge and is not "
            "filled; the answer (Done) stays the filled accent. A tonal button's label reads 4.5 to 1 on its "
            "tint and the tint is the accent's, not the card's. An outlined button's edge is seen at 3 to 1 "
            "on the card and the page; a danger outline is words and edge in the error colour at 4.5 to 1. A "
            "disabled main button is the text colour on a pale fill at about 7 to 1. A roomy button is at "
            "least 36 px tall (40 at Large text). A placeholder reads 4.5 to 1 on its field and on its card, "
            "in both single and multi-line fields, and is drawn in the look's colour, not Qt's default. Time "
            "boxes write their figures at one width."
        ),
        sources=("desktop/native/widgets.py", "desktop/native/look.py", "desktop/native/fonts.py"),
        main=True,
        styles=("widgets",),
    ),
    Screen(
        id="settings.dropdown_list",
        area="settings",
        prepare=dropdown,
        checks=(
            "An open dropdown list uses the look's colours, not Fusion's grey, and marks the chosen row with "
            "the accent across more than 60 % of the row; the other rows stay below 5 % accent."
        ),
        sources=("desktop/native/widgets.py", "desktop/native/look.py"),
        styles=("widgets",),
    ),
    Screen(
        id="settings.toast",
        area="settings",
        prepare=toast,
        checks=(
            "The toast is dark with light words in every look (not a pale card on a light look): words and "
            "Undo each at least 4.5 to 1 on it (7 to 1 in High contrast). Undo is the accent's light "
            "shade on "
            "a light look and the accent itself on a dark one. Its corners are 16 px."
        ),
        sources=("desktop/native/widgets.py", "desktop/native/look.py"),
        main=True,
        styles=("widgets",),
    ),
    Screen(
        id="settings.menu",
        area="settings",
        prepare=menu,
        checks=(
            "A menu opens with its panel's corner at the pointer and its shadow round it: the corner outside "
            "the panel is clear, the panel is solid. The heading (Adding) is drawn as text, at least "
            "one line "
            "tall. The row under the pointer shows against the card and its words keep 4.5 to 1 (7 to 1 in "
            "High contrast, where the row stands off the card by at least 1.5 to 1); the red Delete "
            "keeps 4.5 "
            "to 1 on that row. The menu casts the large shadow in a look with depth and none in a flat one."
        ),
        sources=("desktop/native/menus.py", "desktop/native/look.py"),
        main=True,
        styles=("widgets",),
    ),
    Screen(
        id="settings.next_card_terminal",
        area="settings",
        prepare=next_card_in_terminal,
        checks=(
            "In Terminal the rail's Next card shows its whole time sentence ending '4 h 25 min left': the "
            "sentence wraps and its label is as tall as the wrapped text needs, nothing cut off."
        ),
        sources=("desktop/native/hours/rail.py", "desktop/native/look.py"),
        styles=("widgets",),
    ),
    Screen(
        id="settings.look_preview_side",
        area="settings",
        prepare=look_preview(0, (1400, 900)),
        checks=(
            "At 1400 by 900 the style preview sits on the right of the Look cards, about 60 % of the stage "
            "(between 55 % and 65 %), and its bottom is above the footer. Fit fills that column's width: the "
            "picture is wider than 500 px and at least 1000 px wide in the picture's own size. The preview's "
            "controls sit right under the fitted picture, no more than 16 px below it. Choosing Actual size "
            "gives the preview at least 70 % of the stage's height."
        ),
        sources=LOOK_SOURCES,
        main=True,
        styles=("widgets",),
    ),
    Screen(
        id="settings.look_preview_wide",
        area="settings",
        prepare=look_preview(0, (1600, 1000)),
        checks=(
            "At 1600 by 1000 a wide window gives the preview a real share of the stage: at least 35 % of the "
            "stage's height, with the picture shown at least 240 px tall, so Fit fills the room instead of "
            "squeezing the window picture into a thin strip between empty bars."
        ),
        sources=LOOK_SOURCES,
        styles=("widgets",),
    ),
    Screen(
        id="settings.look_preview_threshold",
        area="settings",
        prepare=look_preview(0, (1000, 800)),
        checks=(
            "At 1000 by 800, the width where the side-by-side layout starts, the preview's controls (the "
            "surface choice and the size choice) are visible and each is at least as wide as it asks for."
        ),
        sources=LOOK_SOURCES,
        styles=("widgets",),
    ),
    Screen(
        id="settings.look_preview_scrolled",
        area="settings",
        prepare=look_preview_scrolled,
        checks=(
            "The Look cards scrolled to their end: the preview has not moved from where it was "
            "unscrolled."
        ),
        sources=LOOK_SOURCES,
        styles=("widgets",),
    ),
    Screen(
        id="settings.look_preview_two_tiles",
        area="settings",
        prepare=look_preview(0, (1050, 800)),
        checks=(
            "At 1050 by 800 (between 1000 and 1100) the Look cards stay wide enough for two tiles on the "
            "first row, level with each other. The preview's controls (the surface choice and the size "
            "choice) are not squeezed: each is at least as wide as it asks for."
        ),
        sources=LOOK_SOURCES,
        styles=("widgets",),
    ),
    Screen(
        id="settings.look_preview_large_text",
        area="settings",
        prepare=look_preview(0, (1280, 800), large=True),
        checks=(
            "At 1280 by 800 with Large text the Look tiles are wider than at Normal text and two "
            "still sit on "
            "a row, beside the preview or, when that no longer fits, under the strip. The preview's controls "
            "are not squeezed. At 1000, 1050 and 1400 wide the same holds."
        ),
        sources=LOOK_SOURCES,
        styles=("widgets",),
    ),
    Screen(
        id="settings.look_preview_strip",
        area="settings",
        prepare=look_preview(0, (900, 700)),
        checks=(
            "Below 1000 px wide the preview stays a strip above the cards at the stage's full width, and "
            "the cards take the full width too."
        ),
        sources=LOOK_SOURCES,
        styles=("widgets",),
    ),
    Screen(
        id="settings.look_preview_short_window",
        area="settings",
        prepare=look_preview(0, (1024, 640), large=True, motion_off=True),
        checks=(
            "At 1024 by 640 with Large text and animations off, the preview sits inside the window (nothing "
            "past the window's right or bottom edge), is at least 160 px wide and 240 px tall, and the Look "
            "cards under it keep at least 200 px to scroll in. The Fit choice is on screen and more than "
            "20 px wide."
        ),
        sources=LOOK_SOURCES,
        main=True,
        styles=("widgets",),
    ),
    Screen(
        id="settings.planning_page_no_preview",
        area="settings",
        prepare=look_preview(1, (1600, 1000)),
        checks=(
            "Another Settings page (Planning) at 1600 by 1000 has no preview and no leftover column: its "
            "cards start at the top of the stage and use the full stage width."
        ),
        sources=("desktop/native/settings.py",),
        styles=("widgets",),
    ),
    Screen(
        id="settings.audit_unfinished_panel",
        area="settings",
        prepare=unfinished_panel,
        checks=(
            "The unfinished-homework panel at 320 by 400: its heading is at the top, the list in the middle "
            "and the dismiss button at the bottom, below the list."
        ),
        sources=("desktop/native/widgets.py",),
        styles=("widgets",),
    ),
    Screen(
        id="settings.audit_timeline_fold",
        area="settings",
        prepare=timeline_fold,
        checks=(
            "Timeline at 1280 by 800 with a fold at 3: the fold handle sits inside the row of day headings "
            "(top at or below 0, bottom within the row) and Wednesday's title ends before the handle, "
            "clear of the fold."
        ),
        sources=("desktop/native/layouts/timeline.py",),
        styles=("widgets",),
    ),
    Screen(
        id="settings.audit_mission_school",
        area="settings",
        prepare=mission_school,
        checks=(
            "Mission control at 1280 by 800: Monday's School block (08:00 to 14:30) lies inside its lane's "
            "track, neither before its left edge nor past its right, with inner clearance for its text."
        ),
        sources=("desktop/native/layouts/mission.py",),
        styles=("widgets",),
    ),
    Screen(
        id="settings.audit_week_list_drawer",
        area="settings",
        prepare=week_list_drawer,
        checks=(
            "Week as a list at 1280 by 800: the panel is a floating overlay exactly 360 px wide and the "
            "planner underneath keeps the width it had without the panel; the drawer does not crush it."
        ),
        sources=("desktop/native/window.py",),
        styles=("widgets",),
    ),
    Screen(
        id="settings.material_tokens",
        area="settings",
        prepare=material_tokens,
        checks=(
            "In Material 3: status words (Done, Due soon, Overdue) in the light mode reach 4.5 to 1 "
            "on white, "
            "and each status word reaches 4.5 to 1 on its own tint; every class bar reaches 3 to 1 on the "
            "card; every block's ink reaches 4.5 to 1 on its fill and is never white or the class colour; "
            "the focus ring reaches 3 to 1 on the card and on the page, in light and dark."
        ),
        sources=("desktop/native/material",),
        main=True,
        styles=("material",),
    ),
]
