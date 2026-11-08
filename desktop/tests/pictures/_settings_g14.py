"""Settings screen for the window chrome: its scroll bar (look check of test_top_bar)."""

from __future__ import annotations

from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_bar_pictures import WIDGETS_DESIGNS


def _settings_page(window: NativeWindow) -> object:
    window.resize(1280, 520)
    window._open_settings()
    wait_until(None, lambda: window._settings is not None and window._settings.isVisible())
    return window._settings.stack.currentWidget()


SCREENS: list[Screen] = [
    Screen(
        id="settings.scroll_bar",
        area="settings",
        prepare=_settings_page,
        checks=(
            "The Settings page's scroll bar, when its content is taller than the window, lies over the "
            "right edge of the content, thin, with no strip kept beside it."
        ),
        sources=("desktop/native/widgets.py", "desktop/native/settings.py"),
        styles=WIDGETS_DESIGNS,
    ),
]
