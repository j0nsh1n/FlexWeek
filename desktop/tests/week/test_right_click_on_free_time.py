"""A right-click on free time opens its menu every time, with a mouse or a touchpad: a press and release
that moves a few pixels still counts."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.light_app import window as light_window  # noqa: F401
from desktop.tests.week.support_drag import (
    WEDNESDAY,
    classic_week,  # noqa: F401
    in_window,
    listed_menus,  # noqa: F401
    press_right_button,
    qapp,  # noqa: F401
)


def test_every_right_click_on_free_time_opens_the_menu(
    qapp: QApplication, classic_week: NativeWindow, listed_menus: list[dict]
) -> None:
    at = in_window(classic_week, WEDNESDAY, 10 * 60)
    for attempt in range(30):
        press_right_button(classic_week, at)
        assert len(listed_menus) == attempt + 1, f"right-click {attempt + 1} opened no menu"
    assert {shown["name"] for shown in listed_menus} == {"spotMenu"}


def test_a_right_click_that_slides_a_few_pixels_still_opens_the_menu(
    qapp: QApplication, classic_week: NativeWindow, listed_menus: list[dict]
) -> None:
    at = in_window(classic_week, WEDNESDAY, 10 * 60)
    for attempt, jitter in enumerate((QPoint(3, 2), QPoint(-2, 4), QPoint(0, -3), QPoint(4, 0))):
        press_right_button(classic_week, at, jitter)
        assert len(listed_menus) == attempt + 1, f"a right-click that moved {jitter} opened no menu"
