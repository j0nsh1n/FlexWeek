"""Pictures of the hours' zoom and scroll: the looks the old zoom tests asserted in pixels and
positions (names over their columns, a long block's name in sight, a held block's words, the zoom
pill and its line). The renderer gathers this module's SCREENS."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from desktop.native.hours.classic import WEEK_SCALE
from desktop.native.weekmodel import build_week
from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.week.support_zoom import (
    ESSAY,
    MONDAY,
    SCHOOL,
    a_day,
    a_hand,
    a_lane_week,
    a_week,
    block_named,
    bridge_of,
    hold_still,
    pump,
    settle,
    show_material,
)

HOURS = ("desktop/native/hours",)
# Standalone views are kept so their hosts and timers outlive the call that made them.
_KEPT: list[QWidget] = []


def _app() -> QApplication:
    app = QApplication.instance()
    assert app is not None
    return app


def _day_names(_window: NativeWindow) -> QWidget:
    view = a_week(_app())
    _KEPT.append(view)
    return view


def _lane_names(_window: NativeWindow) -> QWidget:
    app = _app()
    scroll = a_lane_week(app)
    scroll.scroll_to(6 * 60, above=0)
    settle(app)
    _KEPT.append(scroll)
    return scroll


def _long_name_on_lanes(_window: NativeWindow) -> QWidget:
    app = _app()
    scroll = a_lane_week(app)
    scroll.canvas.set_week(build_week(MONDAY, [SCHOOL], {}, None).occurrences)
    scroll.scroll_to(12 * 60, above=0)
    settle(app)
    _KEPT.append(scroll)
    return scroll


def _held_words_on_lanes(_window: NativeWindow) -> QWidget:
    app = _app()
    scroll = a_lane_week(app, a_hand(words=True))
    canvas = scroll.canvas
    canvas.set_week(build_week(MONDAY, [ESSAY], {}, None).occurrences)
    end = canvas.track_for(3).point_for(20 * 60 + 30).x()
    scroll.horizontalScrollBar().setValue(round(end + 30 - scroll.viewport().width()))
    settle(app)
    hold_still(canvas, 3, 19 * 60 + 45)
    _KEPT.append(scroll)
    return scroll


def _held_words_on_a_column(_window: NativeWindow) -> QWidget:
    app = _app()
    view = a_week(app, [SCHOOL], a_hand(words=True))
    view.scroll.scroll_to(12 * 60, above=0)
    settle(app)
    hold_still(view.hours, 0, 14 * 60)
    _KEPT.append(view)
    return view


def _zoom_pill_at_a_limit(_window: NativeWindow) -> QWidget:
    app = _app()
    view = a_week(app)
    for _ in range(8):
        QTest.mouseClick(view.scroll.buttons.into, Qt.MouseButton.LeftButton)
    assert view.scroll.px == WEEK_SCALE.levels[-1]
    settle(app)
    _KEPT.append(view)
    return view


def _day_heading_today(_window: NativeWindow) -> QWidget:
    view = a_day(_app(), [SCHOOL], 3)
    _KEPT.append(view)
    return view


def _day_heading_another_day(_window: NativeWindow) -> QWidget:
    view = a_day(_app(), [SCHOOL], 1)
    _KEPT.append(view)
    return view


def _material_clinic_at_ten(window: NativeWindow) -> None:
    app = _app()
    session = window.session
    session.add_block(
        {
            "id": "clinic",
            "title": "Clinic",
            "kind": "locked",
            "category": "activity",
            "start": "10:00",
            "duration_min": 60,
            "days": [5],
        }
    )
    session.save()
    root = show_material(app, window)
    window._zoom.pop("material.week", None)
    window._material_page.publish()
    pump(app)
    # One step in from the standard row, so the picture shows the zoomed grid.
    bridge_of(window).zoomBy(1)
    pump(app)
    assert block_named(root, "Clinic") is not None


SCREENS: list[Screen] = [
    Screen(
        id="week.day-names-over-columns",
        area="week",
        prepare=_day_names,
        checks=(
            "Each day's name is centred over its own column, beside the scroll bar, for all seven days "
            "(Monday to Sunday); none is shifted a pixel or more off its column's middle."
        ),
        sources=HOURS,
    ),
    Screen(
        id="week.lane-names-beside-lanes",
        area="week",
        prepare=_lane_names,
        checks=(
            "On lanes scrolled to 06:00, each lane's name (Day 0 to Day 6) is level with the middle of "
            "its own lane, and the names sit in a strip at the left edge of the hours, not over the "
            "lanes themselves; the names stay put while the hours scroll."
        ),
        sources=HOURS,
    ),
    Screen(
        id="week.long-block-name-on-lanes",
        area="week",
        prepare=_long_name_on_lanes,
        checks=(
            "School runs 08:00 to 14:30 and the lanes are scrolled to 12:00, so its start is scrolled "
            "away: its name is still written at the left of what shows (within about 8 px of the left "
            "edge), not at its start off screen."
        ),
        sources=HOURS,
    ),
    Screen(
        id="week.held-block-words-on-lanes",
        area="week",
        prepare=_held_words_on_lanes,
        checks=(
            "The Essay is held near the right edge of what shows; the pill with its times sits fully "
            "inside what shows, not running off past the right edge of the lanes."
        ),
        sources=HOURS,
    ),
    Screen(
        id="week.held-block-words-on-a-column",
        area="week",
        prepare=_held_words_on_a_column,
        checks=(
            "School is held by its end with its start scrolled away above; the pill with its times is "
            "inside what shows, not beside the start off the top."
        ),
        sources=HOURS,
    ),
    Screen(
        id="week.zoom-pill-at-a-limit",
        area="week",
        prepare=_zoom_pill_at_a_limit,
        checks=(
            "At the largest zoom the + button is greyed but still visible, and one caption line "
            "('Largest zoom reached') sits under the pill and above the hours, never covering them. "
            "The pill is 24 px tall; each button is drawn smaller than its 24 px square press area."
        ),
        sources=HOURS,
    ),
    Screen(
        id="week.day-hours-heading-today",
        area="week",
        prepare=_day_heading_today,
        checks=(
            "On Day, the 'Hours' heading is in the same size and the text colour as 'Agenda' beside "
            "it (15 pt, semibold), not the accent colour: today is the day shown."
        ),
        sources=HOURS,
    ),
    Screen(
        id="week.day-hours-heading-another-day",
        area="week",
        prepare=_day_heading_another_day,
        checks=(
            "On Day, the 'Hours' heading reads the same (heading size, text colour, matching "
            "'Agenda') when the day shown is not today; it is not a small muted word."
        ),
        sources=HOURS,
    ),
    Screen(
        id="week.material-week-rows-follow-zoom",
        area="week",
        prepare=_material_clinic_at_ten,
        checks=(
            "Material week, one zoom step in from standard (72 px an hour): Clinic, which starts at "
            "10:00, sits 10 hour rows (720 px) from the top of the grid; at the standard row (56 px) "
            "it sits 560 px down. Blocks line up with the hour lines at both zoom levels."
        ),
        sources=("desktop/native/material", "desktop/native/window.py"),
    ),
]
