"""My day's two screens built on the demo's week (the mock-up's Thursday with School, Soccer and the
History essay), at the sizes and text scales the demo is drawn at."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.layouts.base import Scene
from desktop.native.layouts.dial import DayDialView
from desktop.native.layouts.one_thing import OneThingView
from desktop.native.layouts.registry import options_for, tokens_for
from desktop.native.look import resolved_palette
from desktop.native.weekmodel import build_week, minute_of
from desktop.tests.test_weekmodel import HOMEWORK, WEEK, block

THURSDAY = 3
DEMO_BLOCKS = [
    block("school", "locked", [0, 1, 2, 3, 4], "08:00", 390),
    block("bio-1", "flexible", [2], "17:00", 60, assignment_id="bio"),
    block("soccer", "locked", [3], "16:00", 90, category="exercise"),
    block("essay-1", "flexible", [3], "19:00", 60, assignment_id="essay"),
    block("poster-1", "flexible", [], None, 60, assignment_id="poster"),
    block("math-1", "flexible", [], None, 60, assignment_id="math"),
]
DEMO_HOMEWORK = {
    **HOMEWORK,
    "math": {**HOMEWORK["math"], "title": "Math worksheet", "completed": False},
    "poster": {**HOMEWORK["poster"], "title": "Science poster"},
}


def shown(
    qapp: QApplication,
    view_type: type[OneThingView] | type[DayDialView],
    clock: str,
    width: int = 1280,
    height: int = 800,
    large: bool = False,
    blocks: list[dict] | None = None,
    today: int | None = THURSDAY,
    homework: dict | None = None,
) -> OneThingView | DayDialView:
    layout = "one" if view_type is OneThingView else "dial"
    options = options_for(None, layout)
    palette = resolved_palette("light-frost", False, None, "default")
    week = build_week(WEEK, DEMO_BLOCKS if blocks is None else blocks, homework or DEMO_HOMEWORK)
    view = view_type()
    view.resize(width, height)
    view.show_week(
        Scene(
            week,
            today,
            minute_of(clock),
            options,
            tokens_for(layout, options["look"], palette),
            scale=1.2 if large else 1.0,
        )
    )
    view.show()
    qapp.processEvents()
    return view
