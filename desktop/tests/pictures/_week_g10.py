"""Week pictures that came out of test_layouts_window.py (the lead folds this fragment into
screens_week.py): the main views (designs), the top bar and the looks they wear."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QAbstractButton, QApplication, QWidget

from desktop.native.layouts.registry import LAYOUTS, sanitize_layout
from desktop.native.look import LOOK_DEFAULTS, LOOK_KNOBS, sanitize_look
from desktop.native.window import NativeWindow
from desktop.tests.day.support_layouts_window import (
    busy_thursday,
    own_accent,
    school_week,
    settled,
    signature,
    still,
)
from desktop.tests.pictures.screen import Screen

DESIGNS = ("timeline", "mission", "bento", "retro", "clay")
PLAN_DESIGNS = ("classic", *DESIGNS)


def _use(window: NativeWindow, main: str, day: str = "one") -> None:
    window._layout = {"main": main, "day": day, "options": {}}
    window._day_mode = False
    window.session.set_view("week")
    window._on_week()
    QApplication.processEvents()


def _add_menu(chips: bool) -> Callable[[NativeWindow], object]:
    def prepare(window: NativeWindow) -> object:
        school_week(window)
        window.session.preferences = {**(window.session.preferences or {}), "accent_chips": chips}
        window._on_week()
        QApplication.processEvents()
        window.add_menu.popup(window.mapToGlobal(QPoint(40, 60)))
        QApplication.processEvents()
        return window.add_menu

    return prepare


def _at_size(width: int, height: int) -> Callable[[NativeWindow], object]:
    def prepare(window: NativeWindow) -> object:
        school_week(window)
        window.resize(width, height)
        window.show()
        QApplication.processEvents()
        return None

    return prepare


def _bento(window: NativeWindow) -> object:
    school_week(window)
    _use(window, "bento")
    return None


def _timeline(window: NativeWindow) -> object:
    school_week(window)
    _use(window, "timeline")
    still(window)
    return window.planner.currentWidget()


def _sticky_note(window: NativeWindow) -> object:
    school_week(window)
    session = window.session
    session.add_homework(
        {"id": "poster", "title": "Science poster", "due": f"{session.week_start}T23:59",
         "estimate_min": 60, "revision": 0}
    )  # fmt: skip
    session.save()
    settled(QApplication.instance(), window)
    _use(window, "timeline")
    QApplication.processEvents()
    return window.planner.currentWidget().findChild(QWidget, "timelineWaiting0")


def _timeline_in_paper(window: NativeWindow) -> object:
    school_week(window)
    _use(window, "timeline")
    window._look = sanitize_look({"preset": "paper"})
    window._apply_appearance()
    _use(window, "timeline")
    still(window)
    return window.planner.currentWidget()


def _custom_look(window: NativeWindow) -> object:
    from desktop.native.custom_look import save_look, wear

    school_week(window)
    custom = {
        "name": "Night study",
        "base": "paper",
        "accent": "sea",
        "colours": {"page": "#1e2430", "card": "#262d3b", "text": "#e8ecf2", "line": "#394255"},
        "categories": {"class": {"hue": 140}},
        "corners": 4,
        "heading_font": "mono",
        "text_scale": 1.2,
    }
    window._look = wear(sanitize_look(None), custom)
    window._saved_looks = save_look([], custom, "Night study")
    window._layout = sanitize_layout(
        {**window._layout, "options": {**window._layout["options"], "classic": {"look": "your"}}}
    )
    window._apply_appearance()
    window._on_week()
    settled(QApplication.instance(), window)
    return None


def _surface(main: str, other: bool) -> Callable[[NativeWindow], object]:
    def prepare(window: NativeWindow) -> object:
        school_week(window)
        base = {**(window.session.preferences or {}), "motion": "off"}
        window.session.preferences = base
        knobs = {}
        if other:
            knobs = {"surface": next(v for v in LOOK_KNOBS["surface"] if v != LOOK_DEFAULTS["surface"])}
        window._look = sanitize_look({"preset": "default", "knobs": knobs})
        own = {main: {"look": own_accent(main)}}
        window._layout = sanitize_layout({"main": main, "day": "one", "options": own})
        window._apply_appearance()
        window._on_week()
        for _ in range(20):
            QApplication.processEvents()
        return window.planner.currentWidget()

    return prepare


def _chrome(main: str) -> Callable[[NativeWindow], object]:
    def prepare(window: NativeWindow) -> object:
        school_week(window)
        colour = signature(main)
        window._layout = {"main": main, "day": "one", "options": {main: {"look": colour}}}
        window.session.set_view("week")
        window._apply_appearance()
        window._on_week()
        QApplication.processEvents()
        still(window)
        return window.findChild(QWidget, "weekPage")

    return prepare


def _high_contrast(main: str) -> Callable[[NativeWindow], object]:
    def prepare(window: NativeWindow) -> object:
        school_week(window)
        window.session.preferences = {**(window.session.preferences or {}), "theme_pack": "system"}
        window._look = sanitize_look({"preset": "high-contrast", "knobs": {}})
        _use(window, main, "dial")
        window.findChild(QAbstractButton, "viewWeek").click()
        still(window)
        shown = window.planner.currentWidget()
        return shown.findChild(QWidget, "missionPage") if main == "mission" else shown

    return prepare


def _own_look(main: str) -> Callable[[NativeWindow], object]:
    def prepare(window: NativeWindow) -> object:
        school_week(window)
        window.session.preferences = {**(window.session.preferences or {}), "theme_pack": "light-frost"}
        token = signature(main)
        window._layout = {"main": main, "day": "dial", "options": {main: {"look": token}}}
        window._day_mode = False
        window._apply_appearance()
        window._on_week()
        window.findChild(QAbstractButton, "viewWeek").click()
        still(window)
        return window.planner.currentWidget()

    return prepare


def _fits_a_laptop(main: str) -> Callable[[NativeWindow], object]:
    def prepare(window: NativeWindow) -> object:
        school_week(window)
        busy_thursday(window)
        _use(window, main, "dial")
        return None

    return prepare


def _retro_start(window: NativeWindow) -> object:
    school_week(window)
    window._layout = sanitize_layout({"main": "retro", "day": "one"})
    window._day_mode = False
    window.session.set_view("week")
    window._on_week()
    QApplication.processEvents()
    window.planner.currentWidget().findChild(QWidget, "retroStart").click()
    QApplication.processEvents()
    return None


SOURCES = ("desktop/native/layouts", "desktop/native/window.py", "desktop/native/look.py")

SCREENS: list[Screen] = [
    Screen(
        id="week.add_menu_has_a_colour_per_type",
        area="week",
        prepare=_add_menu(False),
        checks=(
            "The Add menu carries the category colours the chip strip used to: every entry (each type "
            "in CATEGORIES) has its own swatch, so no two types show the same colour (12 px icon, "
            "pixel at 6, 6)."
        ),
        sources=("desktop/native/menus.py", "desktop/native/calendar.py", "desktop/native/window.py"),
    ),
    Screen(
        id="week.add_menu_with_accent_chips",
        area="week",
        prepare=_add_menu(True),
        checks=(
            "With Accent chips on, every type in the Add menu is painted in the accent: all swatches are "
            "one and the same colour."
        ),
        sources=("desktop/native/menus.py", "desktop/native/calendar.py", "desktop/native/window.py"),
    ),
    Screen(
        id="week.title_beside_its_arrows",
        area="week",
        prepare=_at_size(1280, 768),
        checks=(
            "The week title sits after the arrows and Today (Today's right edge is left of the title's "
            "left edge) at 1280 and at 1024 px wide, and at 1280 it is whole: it does not end in an "
            "ellipsis and its text is no wider than the label (\"21 – 27 September\" needs 217 px, "
            "it was given 96 and read \"21 – 27 S\")."
        ),
        sources=("desktop/native/window.py",),
        main=True,
    ),
    Screen(
        id="week.top_bar_keeps_the_gear_at_1024",
        area="week",
        prepare=_at_size(1024, 768),
        checks=(
            "In a 1024 px window Today and the Settings gear are both visible, and the gear's right edge "
            "is inside the window (not past its width, and not wider than the window's minimum)."
        ),
        sources=("desktop/native/window.py",),
    ),
    Screen(
        id="week.bento_fills_the_window",
        area="week",
        prepare=_bento,
        checks="Bento's planner is taller than 80% of the window's height: it fills the window.",
        sources=("desktop/native/layouts/bento.py", "desktop/native/window.py"),
    ),
    Screen(
        id="week.timeline_pages_are_paper",
        area="week",
        prepare=_timeline,
        checks=(
            "Timeline's pages are its paper in the real window: left of the hour labels at half past "
            "twelve (no label there), under the scroll bar at the right edge (clear of its handle), and "
            "right of the zoom beside the week header are all the paper (surface) token, which differs "
            "from the page (bg) token; no grey bands from the window's stylesheet on Qt's plain widgets."
        ),
        sources=("desktop/native/layouts/timeline.py", "desktop/native/window.py"),
    ),
    Screen(
        id="week.timeline_sticky_note_small_print",
        area="week",
        prepare=_sticky_note,
        checks=(
            "A sticky note's small print is regular weight: its title (\"Science\") is bold (600), but "
            "its length (\"1 h\") and due date are regular (400), not as bold as the title (the "
            "window's stylesheet sets every button's font at 600 and a note is a button)."
        ),
        sources=("desktop/native/layouts/timeline.py", "desktop/native/window.py"),
    ),
    Screen(
        id="week.timeline_heading_face",
        area="week",
        prepare=_timeline_in_paper,
        checks=(
            "Changing Timeline's look changes its colours without replacing its own type: the day "
            "names and the figures use the look's heading face (Newsreader on Paper) after the change "
            "and Inter before it."
        ),
        sources=("desktop/native/layouts/timeline.py", "desktop/native/look.py"),
    ),
    Screen(
        id="week.custom_look_dresses_the_window",
        area="week",
        prepare=_custom_look,
        checks=(
            "A custom look \"Night study\" (Paper base, Sea accent, page #1e2430, card #262d3b, text "
            "#e8ecf2, line #394255, School in green hue 140, corners 4, mono headings, text 1.2x) worn "
            "by Today's app: the hours' window colour is #1e2430 and the accent #2dd4bf; School is a "
            "green sunk into the dark card; the week title is in JetBrains Mono; the window's style "
            "sheet has font-size 15.5pt and border-radius 4px; the hours sheet is in the card colour "
            "#262d3b beside the rail on the page."
        ),
        sources=("desktop/native/custom_look.py", "desktop/native/look.py", "desktop/native/window.py"),
        main=True,
    ),
]

SCREENS.append(
    Screen(
        id="week.retro_start_menu_opens_up",
        area="week",
        prepare=_retro_start,
        checks=(
            "Retro's Start button opens More's menu up over the taskbar, as Windows 98's did: the "
            "menu's panel (inside the MENU_EDGE shadow margin) ends at or above the top of the Start "
            "button."
        ),
        sources=("desktop/native/layouts/retro.py", "desktop/native/menus.py"),
    )
)

for _design in DESIGNS:
    for _other in (False, True):
        SCREENS.append(
            Screen(
                id=f"week.{_design}_surface_{'changed' if _other else 'default'}",
                area="week",
                prepare=_surface(_design, _other),
                checks=(
                    f"Surface is a palette token shared by the canvas and the chrome of every design: "
                    f"{LAYOUTS[_design].label} in its own colours with Surface "
                    f"{'set to a non-default value' if _other else 'left at the default'} (animations "
                    "off). The reviewer compares this with its default/changed twin: changing Surface "
                    "must change the picture."
                ),
                sources=SOURCES,
            )
        )

for _design in PLAN_DESIGNS:
    SCREENS.append(
        Screen(
            id=f"week.{_design}_chrome_matches_its_page",
            area="week",
            prepare=_chrome(_design),
            checks=(
                f"{LAYOUTS[_design].label} on its signature look: the week page's top-left pixel (clear "
                "of text and controls) is the design's page colour (bg token) so the top bar and the "
                "canvas wear the same look; under Retro it is the colour of Retro's own title bar."
            ),
            sources=SOURCES,
        )
    )
    SCREENS.append(
        Screen(
            id=f"week.{_design}_in_high_contrast",
            area="week",
            prepare=_high_contrast(_design),
            checks=(
                f"{LAYOUTS[_design].label} with no look of its own on the High contrast look (system pack): "
                "somewhere on the canvas is the account's own palette background #000000 (the design "
                "keeps the account's palette)."
            ),
            sources=SOURCES,
        )
    )
    SCREENS.append(
        Screen(
            id=f"week.{_design}_in_its_signature_look",
            area="week",
            prepare=_own_look(_design),
            checks=(
                f"{LAYOUTS[_design].label} on its signature look in Light frost: somewhere on the applied "
                "canvas is the design's background colour (the panel for Today's app, the desk colour "
                "for Retro, the bg token for the rest), the same colour as the signature look's picture "
                "on the setup page."
            ),
            sources=SOURCES,
        )
    )
    if _design != "classic":
        SCREENS.append(
            Screen(
                id=f"week.{_design}_fits_a_laptop",
                area="week",
                prepare=_fits_a_laptop(_design),
                checks=(
                    f"{LAYOUTS[_design].label} on a busy Thursday (five more commitments, three "
                    "homework with no time yet): the window's minimum size is at most 1366 x 768 so it "
                    "fits a laptop, also at Large text (once signed in the sign-in card's held height "
                    "must not push Retro to 782 px)."
                ),
                sources=SOURCES,
            )
        )
