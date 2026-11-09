"""Week screens for the rail, the Plan and More buttons, the menus and the small-window fits: what
the old week-view tests asserted about sizes and positions, now judged on pictures."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QWidget

from desktop.native import window as window_module
from desktop.native.layouts.base import NARROW_WIDTH
from desktop.native.menus import Menu
from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.week.support_weekview import (
    NORMAL_WINDOW,
    SMALL_WINDOW,
    add_waiting_poster,
    plan_poster_that_cannot_fit,
    pump,
    put_math_essay_on_wednesday,
    put_two_homeworks_on_tuesday,
    set_text_size,
    show_large_classic,
)
from desktop.tests.window_support import still

WINDOW = "desktop/native/window.py"
RAIL = "desktop/native/hours/rail.py"
WIDGETS = "desktop/native/widgets.py"


def _app() -> QApplication:
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    return app


def _folded_rail(window: NativeWindow) -> object:
    add_waiting_poster(_app(), window)
    window.resize(NARROW_WIDTH - 1, 860)
    pump(_app())
    still(window)
    return window.rail


def _plan_buttons(window: NativeWindow) -> object:
    window.resize(900, 800)
    pump(_app(), 6)
    return window.solve_button


def _menus(window: NativeWindow) -> object:
    """The block menu and the free-time menu side by side, each at the size it opens with."""
    put_math_essay_on_wednesday(_app(), window)
    hours = window.week_table.hours
    essay = next(b for b in window.session.blocks if b.get("assignment_id") == "math")
    box = hours.block_rect(essay["id"], 2)
    held: list[Menu] = []

    class Held(Menu):
        def exec(self, *_args: object) -> object:
            held.append(self)
            return None

        def deleteLater(self) -> None:  # kept for the picture
            return None

    real = window_module.Menu
    window_module.Menu = Held
    try:
        window._block_menu(essay["id"], 2, box.center())
        hours.reveal(1, 17 * 60, 17 * 60 + 30)
        _app().processEvents()
        window._spot_menu(1, 17 * 60, hours.point_for(1, 17 * 60))
    finally:
        window_module.Menu = real
    board = QWidget(window)
    board.setLayout(QHBoxLayout())
    for menu in held:
        menu.setParent(board)
        menu.setWindowFlags(Qt.WindowType.Widget)
        menu.adjustSize()
        board.layout().addWidget(menu)
        menu.show()
    board.resize(board.sizeHint())
    board.show()
    return board


def _rail_next_rows(window: NativeWindow) -> object:
    put_two_homeworks_on_tuesday(_app(), window)
    show_large_classic(_app(), window, *SMALL_WINDOW)
    still(window)
    return window.rail


def _plan_result_small(window: NativeWindow) -> object:
    plan_poster_that_cannot_fit(_app(), window)
    show_large_classic(_app(), window, *SMALL_WINDOW)
    still(window)
    return window.plan_review


def _plan_result_normal(window: NativeWindow) -> object:
    plan_poster_that_cannot_fit(_app(), window)
    window.resize(*NORMAL_WINDOW)
    set_text_size(window, "normal", carried=True)
    pump(_app(), 10)
    still(window)
    return window.plan_review


def _plan_result_after_small(window: NativeWindow) -> object:
    plan_poster_that_cannot_fit(_app(), window)
    show_large_classic(_app(), window, *SMALL_WINDOW)
    window.setMinimumSize(0, 0)
    window.resize(*NORMAL_WINDOW)
    set_text_size(window, "normal", carried=True)
    pump(_app(), 10)
    still(window)
    return window.plan_review


def _unfinished_row(window: NativeWindow) -> object:
    window.resize(*NORMAL_WINDOW)
    set_text_size(window, "normal", carried=True)
    panel = window.unfinished_panel
    panel.set_items(
        [
            {
                "id": "bio",
                "title": "Biology",
                "remaining_min": 60,
                "due": "2026-10-12T23:59",
                "left_over_state": "overdue",
                "plannable": True,
            }
        ]
    )
    pump(_app(), 10)
    still(window)
    return panel


SCREENS: list[Screen] = [
    Screen(
        id="week.rail-folded-waiting-chip",
        area="week",
        prepare=_folded_rail,
        checks=(
            "With the window just under the narrow width and Poster (30 min) waiting for a time, the rail"
            " keeps its normal width instead of shrinking or folding away; the line reads 'No time yet"
            " . drag onto a day' and the Poster chip under it is as wide as its own words (once found 0"
            " pixels wide), not a bare line; at 800 wide in Large text the same chip and line still show."
        ),
        sources=(RAIL, WINDOW),
        main=True,
    ),
    Screen(
        id="week.plan-and-more-buttons",
        area="week",
        prepare=_plan_buttons,
        checks=(
            "At 900 wide the Plan button's words (and icon) fit inside the button without being clipped,"
            " in Normal and in Large text; More is icon-only before Plan shortens."
        ),
        sources=(WINDOW,),
    ),
    Screen(
        id="week.block-and-free-time-menus",
        area="week",
        prepare=_menus,
        checks=(
            "The block menu (Open, Copy, one Delete) and the free-time menu are the same width, so they"
            " read as one family when opened one after the other."
        ),
        sources=(WINDOW, "desktop/native/menus.py"),
    ),
    Screen(
        id="week.rail-next-rows-at-small-window",
        area="week",
        prepare=_rail_next_rows,
        checks=(
            "At 1024x640 in Large text the rail keeps its normal width. Each Next row has Start focus"
            " below the name and the time, whole (not cut), and no label or button in the rows or the"
            " Next card overlaps another or is cut. The Next card's Start focus sits below its words."
            " Nothing in the rail (waiting line and count, due labels, Next buttons) runs past its"
            " right edge."
        ),
        sources=(RAIL, WINDOW),
        main=True,
    ),
    Screen(
        id="week.plan-result-at-small-window",
        area="week",
        prepare=_plan_result_small,
        checks=(
            "At 1024x640 in Large text the plan result's buttons wrap below its heading when the row"
            " does not fit; no label or button is cut or overlaps another; left to right the buttons"
            " read Details, Replan all my homework, Got it."
        ),
        sources=(WIDGETS, WINDOW),
        main=True,
    ),
    Screen(
        id="week.plan-result-at-normal-size",
        area="week",
        prepare=_plan_result_normal,
        checks=(
            "At 1280x800 in Normal text the plan result's three buttons share the heading's line"
            " (centres within a few pixels) and read Details, Replan all my homework, Got it left to"
            " right."
        ),
        sources=(WIDGETS, WINDOW),
    ),
    Screen(
        id="week.plan-result-after-a-small-window",
        area="week",
        prepare=_plan_result_after_small,
        checks=(
            "After the window was small (buttons moved below the heading) and grew back to 1280x800 in"
            " Normal text, the plan result's buttons are back on the heading's line, in the order"
            " Details, Replan all my homework, Got it."
        ),
        sources=(WIDGETS, WINDOW),
    ),
    Screen(
        id="week.unfinished-row-at-normal-size",
        area="week",
        prepare=_unfinished_row,
        checks=(
            "At 1280x800 in Normal text each button of an unfinished homework row sits on the same line"
            " as the row's words (centres within a few pixels)."
        ),
        sources=(WIDGETS, WINDOW),
    ),
]
