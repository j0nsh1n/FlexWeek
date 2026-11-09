"""An empty day or week says "Nothing planned", everywhere it is shown.

The same words in the engine's planned line are checked in engine/engine/tests/desk_weekmodel.rs
(test_planned_line_uses_length_label).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QListWidget

from desktop.native.calendar import DAY_FULL
from desktop.native.hours.classic import DaySummary
from desktop.native.layouts.base import Scene
from desktop.native.layouts.bento import planned_words
from desktop.native.layouts.one_thing import OneThingView
from desktop.native.layouts.registry import options_for, tokens_for
from desktop.native.look import resolved_palette
from desktop.native.weekmodel import build_week, minute_of, set_clock_24h
from desktop.native.window import NativeWindow
from desktop.tests.window_support import qapp  # noqa: F401

WEEK = "2026-10-12"


def test_a_day_summary_with_nothing_planned_says_so(qapp: QApplication) -> None:  # noqa: F811
    assert DaySummary().text() == "Nothing planned"


def test_the_bento_design_says_nothing_planned_for_zero_minutes() -> None:
    assert planned_words(0) == "Nothing planned"


def test_an_empty_week_list_says_nothing_planned_for_every_day(qapp: QApplication) -> None:  # noqa: F811
    listing = QListWidget()
    host = SimpleNamespace(
        week_access_list=listing,
        session=SimpleNamespace(planner_view="week"),
        _day_mode=False,
        _show_week_list_row=lambda _shown: None,
    )
    NativeWindow._sync_week_access_list(host, build_week(WEEK, []))
    rows = [listing.item(i).text() for i in range(listing.count())]
    assert rows == [f"{name}: Nothing planned" for name in DAY_FULL]
    assert rows[1] == "Tuesday: Nothing planned"


def test_the_one_thing_design_captions_an_empty_day_as_a_sentence(qapp: QApplication) -> None:  # noqa: F811
    set_clock_24h(True)
    options = options_for(None, "one")
    palette = resolved_palette("light-frost", False, None)
    scene = Scene(
        build_week(WEEK, []),
        3,
        minute_of("13:40"),
        options,
        tokens_for("one", options["look"], palette),
    )
    assert OneThingView()._bar_caption(scene) == "Today, 06:00 to 22:00. Nothing planned."
