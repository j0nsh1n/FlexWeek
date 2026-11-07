"""Pictures of two Settings pages (R3 forms lane, chunk H7): the pixel checks of test_day_pills and
test_steppers, which are about where things sit on the page."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from desktop.tests.pictures.screen import Screen
from desktop.tests.waiting import wait_until

FOCUS, ALERTS = 2, 3


def _settings_at(window, section: int) -> QWidget:
    window._open_settings_at(section)
    wait_until(
        None,
        lambda: window._settings is not None and window._settings.stack.widget(section).isVisible(),
        what="the Settings section showing",
    )
    return window._settings


def _alerts(window) -> QWidget:
    return _settings_at(window, ALERTS)


def _focus(window) -> QWidget:
    return _settings_at(window, FOCUS)


SCREENS: list[Screen] = [
    Screen(
        id="settings.alarm_days_one_row",
        area="settings",
        prepare=_alerts,
        checks=(
            "The alarm's seven day pills (Monday to Sunday) sit on one row: every pill has the same top "
            "edge, none wraps to a second row."
        ),
        sources=("desktop/native/settings.py", "desktop/native/fields.py"),
    ),
    Screen(
        id="settings.focus_steppers_line_up",
        area="settings",
        prepare=_focus,
        checks=(
            "On the Focus page the timer preset box is as wide as the focus fields: its left and right "
            "edges are the same as those of the fields below it, and all the focus steppers share one "
            "left and one right edge."
        ),
        sources=("desktop/native/settings.py", "desktop/native/fields.py"),
    ),
]
