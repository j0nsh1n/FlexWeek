# ruff: noqa: F811
"""Day and Month follow the main view the student picked: a design's Month hides its week surface and
shows its month board, and Today's app keeps its own clock day and chip month."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel, QWidget  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    click,
    qapp,  # noqa: F401
    settled,
    window,  # noqa: F401
)


def test_day_and_month_follow_the_week_layout(qapp: QApplication, window: NativeWindow) -> None:
    window._layout = {"main": "bento", "day": "one", "options": {}}
    click(window, "viewDay")
    assert type(window.planner.currentWidget()).__name__ == "BentoView"
    assert window.planner.currentWidget().scene.surface == "day"
    assert (window.solve_button.isVisible(), window.more_button.isVisible()) == (True, True)
    click(window, "viewMonth")
    settled(qapp, window)
    shown = window.planner.currentWidget()
    assert type(shown).__name__ == "BentoView"
    assert shown.scene.surface == "month"
    click(window, "viewWeek")
    assert (window.solve_button.isVisible(), window.more_button.isVisible()) == (True, True)
    click(window, "viewMyDay")
    assert type(window.planner.currentWidget()).__name__ == "OneThingView"
    assert (window.solve_button.isVisible(), window.more_button.isVisible()) == (True, True)


def test_todays_app_keeps_the_clock_day_and_chip_month(qapp: QApplication, window: NativeWindow) -> None:
    window._layout = {"main": "classic", "day": "one", "options": {}}
    click(window, "viewDay")
    assert window.planner.currentWidget() is window.day_view
    assert window.solve_button.isVisible() is True
    click(window, "viewMonth")
    settled(qapp, window)
    assert window.planner.currentWidget() is window.month_grid


def test_bento_month_hides_the_week_up_next_card(qapp: QApplication, window: NativeWindow) -> None:
    window._layout = {"main": "bento", "day": "one", "options": {}}
    window._on_week()
    qapp.processEvents()
    view = window.planner.currentWidget()
    scroll = view.findChild(QWidget, "bentoScroll")
    assert scroll is not None and scroll.isVisible()
    click(window, "viewMonth")
    settled(qapp, window)
    view = window.planner.currentWidget()
    scroll = view.findChild(QWidget, "bentoScroll")
    assert scroll is not None
    assert scroll.isVisible() is False
    hero = view.findChild(QLabel, "bentoHeroTitle")
    if hero is not None:
        assert hero.isVisible() is False
    board = view.findChild(QWidget, "layoutMonthBoard")
    assert board is not None and board.isVisible()


@pytest.mark.parametrize("layout_id", ["timeline", "mission", "bento", "retro", "clay"])
def test_month_hides_the_whole_week_surface(qapp: QApplication, window: NativeWindow, layout_id: str) -> None:
    window._layout = {"main": layout_id, "day": "one", "options": {}}
    window._day_mode = False
    window.session.set_view("week")
    window._on_week()
    qapp.processEvents()
    view = window.planner.currentWidget()
    host = view._week_host()
    assert host is not None and host.isVisible()
    click(window, "viewMonth")
    settled(qapp, window)
    view = window.planner.currentWidget()
    host = view._week_host()
    assert host is not None
    assert host.isVisible() is False
    board = view.findChild(QWidget, "layoutMonthBoard")
    assert board is not None and board.isVisible()
