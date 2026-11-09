"""What every main view owes the student, whichever design and whichever options: by itself it shows
everything that has no time yet, opens any block on screen, and reaches every day of the week. The
mock-up measured this; the native client tests it. Add, Plan and My day are the top bar's in every
design since 0.17 (the window tests check Add there), so a design draws no second Add.
"""

# ruff: noqa: E402, F811  (pytest fixtures imported by name)
from __future__ import annotations

import itertools

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton

from desktop.native.layouts.base import LayoutView, Scene
from desktop.native.layouts.registry import LAYOUTS, tokens_for
from desktop.native.layouts.views import VIEW_CLASSES
from desktop.native.look import design_look
from desktop.native.weekmodel import build_week, minute_of
from desktop.tests.test_weekmodel import BLOCKS, HOMEWORK, TRACE, WEEK, block
from desktop.tests.window_support import qapp  # noqa: F401

MAIN_VIEWS = [layout_id for layout_id in VIEW_CLASSES if LAYOUTS[layout_id].role == "plan"]

WAITING = [
    *BLOCKS,
    block("second-wait", "flexible", [], None, 45, assignment_id="essay", title="Second wait"),
]


def every_choice(layout_id: str) -> list[dict[str, str]]:
    options = LAYOUTS[layout_id].options
    return [
        dict(zip([option.key for option in options], values, strict=True))
        for values in itertools.product(*[option.values for option in options])
    ]


def shown(layout_id: str, options: dict[str, str], today: int | None = 3) -> LayoutView:
    week = build_week(WEEK, WAITING, HOMEWORK, TRACE)
    view = VIEW_CLASSES[layout_id]()
    view.resize(1366, 700)
    page_palette, _look = design_look(options["look"], "light-frost", False, None)
    tokens = tokens_for(layout_id, options["look"], page_palette)
    view.show_week(Scene(week, today, minute_of("13:40"), options, tokens))
    return view


def blocks_offered(view: LayoutView) -> set[str]:
    return {item.property("block_id") for item in view.findChildren(QPushButton)} - {None}


@pytest.mark.parametrize("layout_id", MAIN_VIEWS)
def test_a_main_view_can_plan_by_itself_whatever_its_options(qapp: QApplication, layout_id: str) -> None:
    for options in every_choice(layout_id):
        view = shown(layout_id, options)
        assert {"poster-1", "second-wait"} <= blocks_offered(view), options


@pytest.mark.parametrize("layout_id", MAIN_VIEWS)
def test_a_main_view_reaches_every_day_of_the_week(qapp: QApplication, layout_id: str) -> None:
    for options in every_choice(layout_id):
        view = shown(layout_id, options)
        everything = {"school", "dinner", "essay-1", "chem-1", "math-1"}
        days = {item.property("day_target") for item in view.findChildren(QPushButton)} - {None}
        assert everything <= blocks_offered(view) or days == set(range(7)), options


@pytest.mark.parametrize("layout_id", MAIN_VIEWS)
def test_a_main_views_buttons_ask_for_the_right_thing(qapp: QApplication, layout_id: str) -> None:
    view = shown(layout_id, every_choice(layout_id)[0])
    asked: list[str] = []
    view.add_requested.connect(lambda _category: asked.append("add"))
    view.plan_requested.connect(lambda: asked.append("plan"))
    view.my_day_requested.connect(lambda: asked.append("my day"))
    view.block_activated.connect(asked.append)
    next(item for item in view.findChildren(QPushButton) if item.property("block_id") == "poster-1").click()
    assert asked == ["poster-1"]


@pytest.mark.parametrize("layout_id", MAIN_VIEWS)
def test_a_main_view_survives_an_empty_week_and_another_week(qapp: QApplication, layout_id: str) -> None:
    options = every_choice(layout_id)[0]
    page_palette, _look = design_look(options["look"], "light-frost", False, None)
    tokens = tokens_for(layout_id, options["look"], page_palette)
    for today in (3, None):
        view = VIEW_CLASSES[layout_id]()
        view.show_week(Scene(build_week(WEEK, [], {}, None), today, minute_of("13:40"), options, tokens))
        assert not view.grab().isNull()
