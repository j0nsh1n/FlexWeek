"""My day pictures that came out of test_layouts_window.py (the lead folds this fragment into
screens_myday.py)."""

from __future__ import annotations

from PySide6.QtWidgets import QAbstractButton, QApplication

from desktop.native.layouts.registry import LAYOUTS
from desktop.native.look import sanitize_look
from desktop.native.window import NativeWindow
from desktop.tests.day.support_layouts_window import busy_thursday, school_week, signature, still
from desktop.tests.pictures.screen import Screen


def _open_my_day(window: NativeWindow) -> object:
    window.findChild(QAbstractButton, "viewMyDay").click()
    still(window)
    return window.planner.currentWidget()


def _one_thing_in_paper(window: NativeWindow) -> object:
    school_week(window)
    window._look = {"preset": "paper", "knobs": {"corners": "rounded"}}
    window._layout = {"main": "classic", "day": "one", "options": {"one": {"look": "preset:one-paper"}}}
    window._save_look()
    window._load_look()
    return _open_my_day(window)


def _one_thing_in_terminal(window: NativeWindow) -> object:
    school_week(window)
    window._layout = {"main": "classic", "day": "one", "options": {"one": {"look": "your"}}}
    _open_my_day(window)
    window._look = {"preset": "terminal", "knobs": {}}
    window._apply_appearance()
    still(window)
    return window.planner.currentWidget()


def _dial_list(window: NativeWindow) -> object:
    school_week(window)
    window._layout = {"main": "classic", "day": "dial", "options": {}}
    return _open_my_day(window)


def _shrunk_after_a_tall_window(window: NativeWindow) -> object:
    school_week(window)
    window._day_mode = True
    window._layout = {"main": "classic", "day": "one", "options": {}}
    window._on_week()
    window.resize(1100, 1000)
    QApplication.processEvents()
    window.resize(1100, 700)
    QApplication.processEvents()
    return None


def _fits_a_laptop(layout_id: str):
    def prepare(window: NativeWindow) -> object:
        school_week(window)
        busy_thursday(window)
        window._day_mode = True
        window._layout = {"main": "classic", "day": layout_id, "options": {}}
        window._on_week()
        QApplication.processEvents()
        return None

    return prepare


def _day_in_high_contrast(layout_id: str):
    def prepare(window: NativeWindow) -> object:
        school_week(window)
        window.session.preferences = {**(window.session.preferences or {}), "theme_pack": "system"}
        window._look = sanitize_look({"preset": "high-contrast", "knobs": {}})
        window._layout = {"main": "classic", "day": layout_id, "options": {}}
        window._day_mode = True
        window._on_week()
        return _open_my_day(window)

    return prepare


def _day_in_its_own_look(layout_id: str):
    def prepare(window: NativeWindow) -> object:
        school_week(window)
        window.session.preferences = {**(window.session.preferences or {}), "theme_pack": "light-frost"}
        token = signature(layout_id)
        window._layout = {"main": "classic", "day": layout_id, "options": {layout_id: {"look": token}}}
        window._day_mode = True
        window._apply_appearance()
        window._on_week()
        return _open_my_day(window)

    return prepare


SCREENS: list[Screen] = [
    Screen(
        id="myday.one_thing_in_the_paper_look",
        area="myday",
        prepare=_one_thing_in_paper,
        checks=(
            "One thing, opened from My day with the saved layout (day 'one', look 'preset:one-paper') on "
            "the Paper look, paints its page in the Paper cream #f7f1e3 (the old test read the pixel at "
            "4, 4)."
        ),
        sources=("desktop/native/layouts/one_thing.py", "desktop/native/look.py"),
    ),
    Screen(
        id="myday.one_thing_follows_the_look",
        area="myday",
        prepare=_one_thing_in_terminal,
        checks=(
            "One thing set to the look 'your' repaints when the look changes to Terminal: its page colour "
            "is the Terminal look's background and no longer the default look's (the old test compared "
            "the pixel at 4, 4 before and after and against the scene's background token)."
        ),
        sources=("desktop/native/layouts/one_thing.py", "desktop/native/look.py"),
    ),
    Screen(
        id="myday.dial_list_is_one_card",
        area="myday",
        prepare=_dial_list,
        checks=(
            "The day dial's list is one card: right of the last row's words, 8 px in from the list's "
            "right edge, the colour is the surface token (the card), not a grey band the window's "
            "stylesheet paints on plain widgets."
        ),
        sources=("desktop/native/layouts/dial.py",),
    ),
    Screen(
        id="myday.one_thing_shrinks_to_a_laptop",
        area="myday",
        prepare=_shrunk_after_a_tall_window,
        checks=(
            "At Large text, My day in One thing: after the window is dragged to 1100 x 1000 and back to "
            "1100 x 700 the window is 700 px high, not 50 px taller than asked (the ring is fixed at the "
            "size the height last gave it)."
        ),
        sources=("desktop/native/layouts/one_thing.py", "desktop/native/window.py"),
    ),
    *[
        Screen(
            id=f"myday.{spec.id}_fits_a_laptop",
            area="myday",
            prepare=_fits_a_laptop(spec.id),
            checks=(
                f"The {spec.label} day screen on a busy Thursday (five more commitments, three homework "
                "with no time yet) leaves the window's minimum size at most 1366 x 768 so it fits a "
                "laptop, at Large text too: nothing is cut or pushed past the bottom edge."
            ),
            sources=(f"desktop/native/layouts/{'dial' if spec.id == 'dial' else 'one_thing'}.py",),
        )
        for spec in LAYOUTS.values()
        if spec.role == "day"
    ],
    *[
        Screen(
            id=f"myday.{spec.id}_in_high_contrast",
            area="myday",
            prepare=_day_in_high_contrast(spec.id),
            checks=(
                f"The {spec.label} day screen with no look of its own on the High contrast look (system "
                "pack): somewhere on the canvas is the account's own palette background #000000."
            ),
            sources=("desktop/native/layouts", "desktop/native/look.py"),
        )
        for spec in LAYOUTS.values()
        if spec.role == "day"
    ],
    *[
        Screen(
            id=f"myday.{spec.id}_in_its_signature_look",
            area="myday",
            prepare=_day_in_its_own_look(spec.id),
            checks=(
                f"The {spec.label} day screen on its signature look in Light frost: somewhere on the "
                "applied canvas is the design's background (bg token), the same colour as the signature "
                "look's picture on the setup page."
            ),
            sources=("desktop/native/layouts", "desktop/native/look.py"),
        )
        for spec in LAYOUTS.values()
        if spec.role == "day"
    ],
]
