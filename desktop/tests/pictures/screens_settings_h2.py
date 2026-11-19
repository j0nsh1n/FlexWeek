"""Settings pictures: the looks and their colours, the controls, the toast and menus, and the audit screens
(R3.4 forms lane, chunk H2). The checks are what the old code tests asserted about colours, contrast,
positions and sizes, with their numbers."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from desktop.native.weekmodel import WeekModel
from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.settings import support_pictures as pictures
from desktop.tests.window_support import still


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
