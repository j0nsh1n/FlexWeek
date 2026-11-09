"""Pictures of the Week's rail (Today's app) and the Material week: the looks their old code tests
asserted in pixels, now judged on a picture. The renderer gathers this module's SCREENS."""

from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtWidgets import QApplication, QWidget

from backend.tests.fake_clock import CLOCK
from desktop.native.calendar import sunday_due
from desktop.native.hours.hand import Hand, Verdict
from desktop.native.hours.rail import Rail
from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.week.support_material import (
    _look,
    _reset,
    _show_material,
    pump,
    seed_material_week,
    seeded,
)
from desktop.tests.window_support import settled

RAIL = ("desktop/native/hours/rail.py", "desktop/native/window.py")
MATERIAL = ("desktop/native/material", "desktop/native/window.py")


def _app() -> QApplication:
    app = QApplication.instance()
    assert app is not None
    return app


def _rail_week(window: NativeWindow) -> None:
    seeded(_app(), window)


def _rail_timer(window: NativeWindow) -> None:
    app = _app()
    seeded(app, window)
    essay = next(block for block in window.session.blocks if block.get("assignment_id") == "essay")
    window.session.start_focus(essay["id"], 3)
    app.processEvents()
    window._on_week()
    pump(app)


def _rail_chips(window: NativeWindow) -> None:
    app = _app()
    seeded(app, window)
    session = window.session
    session.add_homework(
        {
            "id": "poster",
            "title": "Science poster for the fair",
            "due": sunday_due(session.week_start),
            "estimate_min": 90,
            "revision": 0,
        }
    )
    session.save()
    settled(app, window)
    pump(app)


def _rail_narrow(window: NativeWindow) -> None:
    app = _app()
    seeded(app, window)
    window.resize(1100, 860)
    pump(app)


def _rail_next_start_focus(window: NativeWindow) -> None:
    app = _app()
    seeded(app, window)
    session = window.session
    CLOCK.set(datetime.fromisoformat(session.week_start) + timedelta(hours=19))
    session.week_changed.emit()
    settled(app, window)
    math = next(block for block in session.blocks if block.get("assignment_id") == "math")
    session.add_block({**math, "start": "17:00", "days": [4], "pinned": True})
    session.save()
    settled(app, window)
    pump(app)


def _rail_one_go(window: NativeWindow) -> None:
    app = _app()
    seeded(app, window)
    window.rail.set_week(
        window.rail._week,
        window.rail._today,
        window.rail._minute,
        {"chemistry": {"title": "Long chemistry report", "due": sunday_due(window.session.week_start)}},
        [{"assignment_id": "chemistry", "title": "Long chemistry report", "minutes": 2400}],
        {"chemistry"},
    )
    app.processEvents()


def _rail_many_rows(window: NativeWindow) -> None:
    app = _app()
    seeded(app, window)
    window.rail.set_tasks(
        [{"id": f"t{n}", "day": 4, "start": "17:00", "title": f"Task {n}"} for n in range(9)], 0
    )
    app.processEvents()


def _rail_focus_row(window: NativeWindow) -> QWidget:
    """The rail alone, with one early focus row whose name is long, so its time must stay whole."""
    from PySide6.QtGui import QFont

    from desktop.native.fonts import load_fonts
    from desktop.native.look import resolved_palette

    load_fonts()
    host = QWidget()
    rail = Rail(Hand(lambda *_a, **_k: Verdict(True, ""), host))
    rail.setFont(QFont("Inter", 11))
    rail.set_look(None, resolved_palette("system", False, None))
    rail.set_tasks(
        [{"id": "essay", "title": "History essay that is quite long", "day": 0, "start": "06:00"}], 3
    )
    rail.resize(280, 120)
    # The picture's owner is the window, so the host outlives this call.
    window._picture_host = host
    rail.tasks.resize(280, 60)
    return rail.tasks


def _day_header(window: NativeWindow) -> None:
    app = _app()
    seeded(app, window)
    window.resize(810, 860)
    pump(app)


def _material(window: NativeWindow) -> None:
    app = _app()
    seed_material_week(window, app)
    _reset(window, app)


def _material_with_saturday(window: NativeWindow, weekends: bool) -> None:
    app = _app()
    seed_material_week(window, app)
    window.session.add_block(
        {
            "id": "sat",
            "title": "Match",
            "kind": "locked",
            "category": "extra",
            "start": "10:00",
            "duration_min": 60,
            "days": [5],
        }
    )
    window.session.save()
    settled(app, window)
    _reset(window, app)
    if not weekends:
        window.session.preferences = {**(window.session.preferences or {}), "show_weekends": False}
        window._material_page.publish()
        pump(app, 30)


def _material_dropped(window: NativeWindow) -> None:
    app = _app()
    seed_material_week(window, app)
    session = window.session
    session.add_homework(
        {
            "id": "sheet",
            "title": "Math worksheet",
            "due": sunday_due(session.week_start),
            "estimate_min": 30,
            "revision": 0,
        }
    )
    session.save()
    settled(app, window)
    block = next(block for block in session.blocks if block.get("assignment_id") == "sheet")
    session.add_block({**block, "start": "16:00", "days": [4]})
    session.save()
    settled(app, window)
    _reset_keeping_blocks(window)


def _reset_keeping_blocks(window: NativeWindow) -> None:
    app = _app()
    window.session.preferences = {
        **(window.session.preferences or {}),
        "show_weekends": True,
        "clock_24h": True,
    }
    _show_material(app, window)
    window._material_page.publish()
    pump(app, 30)


def _material_compact(window: NativeWindow) -> None:
    app = _app()
    seed_material_week(window, app)
    _reset(window, app)
    _look(window, density="compact")
    _show_material(app, window)


SCREENS: list[Screen] = [
    Screen(
        id="week.rail-beside-the-hours",
        area="week",
        prepare=lambda window: _rail_week(window),
        checks=(
            "The rail sits to the left of the hours at its slim fixed width, and the week takes the rest of "
            "the window width (within 24 px). The calendar sits directly under the top bar, less than 32 px "
            "below it, with no status strip. The Next card starts near the top of the rail (under 40 px). "
            "The Next card, Not placed yet chips and focus list read in the rail."
        ),
        sources=RAIL,
        main=True,
    ),
    Screen(
        id="week.rail-running-timer",
        area="week",
        prepare=lambda window: _rail_timer(window),
        checks=(
            "The running timer is the rail's first card, above Next, as one compact line that fits the rail "
            "width (no wider than the rail) with the end 'left' visible and nothing cut, also at Large text."
        ),
        sources=RAIL,
        main=True,
    ),
    Screen(
        id="week.rail-chips-and-high-contrast",
        area="week",
        prepare=lambda window: _rail_chips(window),
        checks=(
            "Two chips in Not placed yet: each name is on at most two lines and no chip runs past the rail's "
            "right edge. The rail keeps its fixed width, the focus list shows no sideways scroll bar and no "
            "row is cut. In High contrast the waiting count is plain text, with no filled badge or rounded "
            "border."
        ),
        sources=RAIL,
        main=True,
    ),
    Screen(
        id="week.rail-at-the-narrow-window",
        area="week",
        prepare=lambda window: _rail_narrow(window),
        checks=(
            "At 1100 px the rail keeps its full slim width (it does not fold) and the blocks keep their "
            "whole times."
        ),
        sources=RAIL,
    ),
    Screen(
        id="week.rail-next-card-start-focus",
        area="week",
        prepare=lambda window: _rail_next_start_focus(window),
        checks=(
            "The Next card's 'Start focus' button and the card's right foot stay inside the rail's width."
        ),
        sources=RAIL,
    ),
    Screen(
        id="week.rail-one-go-message",
        area="week",
        prepare=lambda window: _rail_one_go(window),
        checks=(
            "The 'does not fit in one go' message wraps in at most four lines inside the rail at Large text; "
            "'Allow splitting' sits on its own line below the message and its whole words are not clipped."
        ),
        sources=RAIL,
    ),
    Screen(
        id="week.rail-many-focus-rows",
        area="week",
        prepare=lambda window: _rail_many_rows(window),
        checks=(
            "Nine focus rows do not change the rail's height (the rail scrolls as a whole) and no row is "
            "clipped."
        ),
        sources=RAIL,
    ),
    Screen(
        id="week.rail-focus-row-time",
        area="week",
        prepare=lambda window: _rail_focus_row(window),
        checks=(
            "In a focus row 'Mon 06:00' is written whole and inside the row; the long name is what is "
            "shortened, not the time."
        ),
        sources=("desktop/native/hours/rail.py",),
    ),
    Screen(
        id="week.day-header-homework-length",
        area="week",
        prepare=lambda window: _day_header(window),
        checks=(
            "At 810 px each day header writes its homework length whole ('1h' or '1h 30m'), never cut by the "
            "column edge, and it does not read as a time of day."
        ),
        sources=("desktop/native/hours/classic.py", "desktop/native/layouts/base.py"),
        main=True,
    ),
    Screen(
        id="week.material-plan-button-disabled",
        area="week",
        prepare=lambda window: _material(window),
        checks=(
            "With nothing waiting, the Plan my homework button is a text button with no fill, and its words "
            "stay readable: the muted ink at full opacity, not the 38 % disabled ink."
        ),
        sources=MATERIAL,
        styles=("material",),
    ),
    Screen(
        id="week.material-dropped-block",
        area="week",
        prepare=lambda window: _material_dropped(window),
        checks=(
            "A homework dropped on Friday 16:00 is drawn with its top at the 16:00 hour line (16 hour rows "
            "down the grid)."
        ),
        sources=MATERIAL,
        styles=("material",),
    ),
    Screen(
        id="week.material-past-blocks-dimmed",
        area="week",
        prepare=lambda window: _material(window),
        checks=(
            "At Thursday 19:00 the past School blocks (Monday to Thursday) are dimmed: fill and bar at 55 % "
            "opacity, the title at full opacity. Friday's School and the essay in progress are fully opaque."
        ),
        sources=MATERIAL,
        styles=("material",),
        main=True,
    ),
    Screen(
        id="week.material-seven-columns",
        area="week",
        prepare=lambda window: _material_with_saturday(window, True),
        checks=(
            "Seven equal day columns fill the grid beside the hour gutter; the Saturday Match block shows."
        ),
        sources=MATERIAL,
        styles=("material",),
    ),
    Screen(
        id="week.material-weekdays-only",
        area="week",
        prepare=lambda window: _material_with_saturday(window, False),
        checks=(
            "Five day columns fill the same grid, each 40 % wider than a day in the seven-column week "
            "(grid width / 5 against / 7); no Saturday or Sunday column or block."
        ),
        sources=MATERIAL,
        styles=("material",),
    ),
    Screen(
        id="week.material-compact-rows",
        area="week",
        prepare=lambda window: _material_compact(window),
        checks=(
            "With compact density the hour rows are 44 px: the essay starts at 18:45 (18.75 rows down), "
            "School starts at 08:00 and is 6.5 rows less 2 px tall."
        ),
        sources=MATERIAL,
        styles=("material",),
    ),
    Screen(
        id="week.material-block-words-and-bars",
        area="week",
        prepare=lambda window: _material(window),
        checks=(
            "Light and dark: every block title reaches 4.5:1 contrast on its fill as drawn, past blocks "
            "included, with no fade from any ancestor; a current block's bar reaches 3:1 on the ground "
            "(page or today's card) beside it."
        ),
        sources=MATERIAL,
        styles=("material",),
        main=True,
    ),
    Screen(
        id="week.material-now-line",
        area="week",
        prepare=lambda window: _material(window),
        checks=(
            "The now line runs behind every block (inside a block's title row the pixel is the block fill) "
            "and over empty grid it is the line colour; its dot stays on top of the blocks; a homework "
            "held over a slot outlines it above the line."
        ),
        sources=MATERIAL,
        styles=("material",),
    ),
    Screen(
        id="week.material-today-header",
        area="week",
        prepare=lambda window: _material(window),
        checks=(
            "Only today's date circle in the day headers is filled, in the primary colour; the other six "
            "have no fill."
        ),
        sources=MATERIAL,
        styles=("material",),
    ),
]
