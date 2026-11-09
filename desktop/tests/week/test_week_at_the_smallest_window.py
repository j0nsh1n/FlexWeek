"""At the smallest supported window with Large text the rail still lists what is next, and a plan
that cannot fit everything still shows its result with its three buttons. How they fit is a
picture (screens week.rail-next-rows-at-small-window and week.plan-result-*)."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.week.support_weekview import (
    HOMEWORK_MINUTES,
    NORMAL_WINDOW,
    PLAN_BUTTONS,
    SMALL_WINDOW,
    plan_poster_that_cannot_fit,
    pump,
    put_two_homeworks_on_tuesday,
    set_text_size,
    show_large_classic,
)
from desktop.tests.window_support import qapp, settled  # noqa: F401


def test_homework_later_today_appears_under_next_with_start_focus(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    put_two_homeworks_on_tuesday(qapp, window)
    show_large_classic(qapp, window, *SMALL_WINDOW)
    rows = window.rail.next.rest.findChildren(QWidget, "railNextRow")
    assert rows, "homework later today appears under Next"
    for row in rows:
        assert row.findChild(QPushButton, "railNextRowFocus") is not None, "homework row has Start focus"
    assert window.rail.next.start_focus is not None


def test_a_plan_that_cannot_fit_shows_its_result_with_details_replan_and_got_it(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    plan_poster_that_cannot_fit(qapp, window)
    show_large_classic(qapp, window, *SMALL_WINDOW)
    assert window.plan_review.isVisible(), "the plan result is present"
    for name in PLAN_BUTTONS:
        button = window.plan_review.findChild(QPushButton, name)
        assert button is not None and button.isVisible(), f"{name} is on the plan result"


def test_the_plan_result_keeps_its_buttons_after_a_small_window_and_back(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    plan_poster_that_cannot_fit(qapp, window)
    show_large_classic(qapp, window, *SMALL_WINDOW)
    window.setMinimumSize(0, 0)
    window.resize(*NORMAL_WINDOW)
    set_text_size(window, "normal", carried=True)
    pump(qapp, 10)
    assert window.plan_review.isVisible()
    for name in PLAN_BUTTONS:
        button = window.plan_review.findChild(QPushButton, name)
        assert button is not None and button.isVisible(), f"{name} is back on the plan result"


def test_an_overdue_unfinished_row_has_its_text_and_buttons(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    window.resize(*NORMAL_WINDOW)
    set_text_size(window, "normal", carried=True)
    panel = window.unfinished_panel
    panel.set_items(
        [
            {
                "id": "bio",
                "title": "Biology",
                "remaining_min": HOMEWORK_MINUTES,
                "due": "2026-10-12T23:59",
                "left_over_state": "overdue",
                "plannable": True,
            }
        ]
    )
    pump(qapp, 10)
    row = panel.list.itemWidget(panel.list.item(0))
    assert row.findChild(QLabel, "unfinishedRow") is not None
    assert row.findChildren(QPushButton)
