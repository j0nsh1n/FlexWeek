# ruff: noqa: F811
"""Changing view moves the way the animation setting says: the new page is live at once while the old
one fades or the new one slides in, Settings slides over the week, and Animations off turns every fade
off. Every wait is for the motion to end, never a fixed time."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from desktop.native.motion import SLIDE_NAME, busy  # noqa: E402
from desktop.native.settings import SettingsPage  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    at_motion_level,
    click,
    combo,
    fades,
    qapp,  # noqa: F401
    wait_until,
    window,  # noqa: F401
)


def _moving(window: NativeWindow) -> bool:
    slides = [label for label in window._stack.findChildren(QLabel, SLIDE_NAME) if label.isVisible()]
    return bool(fades(window) or slides or busy())


def _over(qapp: QApplication, window: NativeWindow) -> None:
    wait_until(qapp, lambda: not _moving(window), what="the fades and slides ending")


def test_a_new_view_is_live_at_once_while_the_old_one_fades(qapp: QApplication, window: NativeWindow) -> None:
    at_motion_level(qapp, window, "normal")
    title = window.week_title
    week_title = title.full_text()
    click(window, "viewDay")
    day = window._planner_widget("day")
    assert window.planner.currentWidget() is day
    assert title.full_text() != week_title
    assert len(fades(window)) == 1, "the old page only: the title has no picture of its own"
    assert title.graphicsEffect() is None, "the new title is not faded: both were seen overlapping"
    effect = day.graphicsEffect()
    assert effect.opacity == 0, "Day starts under the week, which is still there"
    assert effect.offset.x() < 0, "and comes in from the left, where its segment is"
    _over(qapp, window)
    assert title.graphicsEffect() is None
    assert fades(window) == [] and day.graphicsEffect() is None
    click(window, "viewWeek")
    assert window.planner.currentWidget().graphicsEffect().offset.x() > 0, "Week comes in from the right"
    _over(qapp, window)


def test_settings_slide_in_over_the_week_and_away_again(qapp: QApplication, window: NativeWindow) -> None:
    at_motion_level(qapp, window, "normal")
    window._open_settings()
    settings = window._settings
    assert window._stack.currentWidget() is settings
    (coming,) = [label for label in window._stack.findChildren(QLabel, SLIDE_NAME) if label.isVisible()]
    assert coming.x() == window._stack.width(), "from the right edge"
    (week,) = fades(window._stack)
    _over(qapp, window)
    assert fades(window) == [] and settings.graphicsEffect() is None
    assert window._stack.findChildren(QLabel, SLIDE_NAME) == [] or not coming.isVisible()
    settings.close_page()
    assert window._stack.currentWidget().objectName() == "weekPage", "the week is live at once"
    (leaving,) = fades(window._stack)
    _over(qapp, window)
    assert fades(window) == []


def test_the_next_week_slides_in_as_the_last_one_drifts_away(
    qapp: QApplication, window: NativeWindow
) -> None:
    at_motion_level(qapp, window, "normal")
    start = window.session.week_start
    click(window, "nextWeek")
    assert window._travel_direction == -1
    wait_until(qapp, lambda: window.session.week_start != start and not window.session.busy)
    _over(qapp, window)
    assert fades(window) == []


def test_animations_off_turns_every_fade_off(qapp: QApplication, window: NativeWindow) -> None:
    at_motion_level(qapp, window, "off")
    assert window._motion == "off"
    click(window, "viewMonth")
    assert fades(window) == []
    assert window.planner.currentWidget().graphicsEffect() is None
    dialog = SettingsPage(None, window.session.preferences, window._look, {}, window._layout)
    assert combo(dialog, "prefMotion").currentData() == "off"
    assert dialog.updates()["motion"] == "off"
