"""Ctrl with =, - and 0 are the window's: they zoom whichever hours are showing, in Today's app and in
every design, wherever the keyboard is. They used to work only while the hours themselves had the
keyboard, which a click on Day, Week or a block's editor took away."""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from backend.tests.fake_clock import CLOCK

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QStandardPaths, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QAbstractButton, QApplication

    from desktop.native.hours.zoom import HoursScroll
    from desktop.native.layouts.registry import sanitize_layout
    from desktop.native.window import NativeWindow
    from desktop.tests.light_app import open_light  # noqa: F401
    from desktop.tests.waiting import wait_until  # noqa: F401

PASSWORD = "a-long-test-password"
DESIGNS = ("classic", "timeline", "mission", "bento", "retro", "clay")
# Ctrl and 0, =, =, - and 0 again, and the pixels an hour each surface shows after each.
PRESSES = ("0", "=", "=", "-", "0")
LEVELS = {
    ("classic", "week"): [48, 64, 96, 64, 48],
    ("classic", "day"): [96, 128, 160, 128, 96],
    ("timeline", "week"): [36, 48, 64, 48, 36],
    ("timeline", "day"): [45, 60, 80, 60, 45],
    ("mission", "week"): [56, 72, 96, 72, 56],
    ("mission", "day"): [56, 72, 96, 72, 56],
    ("bento", "week"): [44, 64, 96, 64, 44],
    ("bento", "day"): [44, 64, 96, 64, 44],
    ("retro", "week"): [40, 56, 72, 56, 40],
    ("retro", "day"): [40, 56, 72, 56, 40],
    ("clay", "week"): [38, 48, 64, 48, 38],
    ("clay", "day"): [38, 48, 64, 48, 38],
}
KEYS = {"=": Qt.Key.Key_Equal, "-": Qt.Key.Key_Minus, "0": Qt.Key.Key_0}


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-zoom-keys-test"])


def look_file() -> Path:
    root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(root) / "flexweek-look.json"


@pytest.fixture()
def window(qapp: QApplication, open_light: Callable[..., NativeWindow]) -> Iterator[NativeWindow]:
    """Signed in, with School on weekdays and the clock held at Thursday 15:40. No zoom is remembered."""
    made = open_light((1280, 860))
    session = made.session
    thursday = datetime.fromisoformat(session.week_start) + timedelta(days=3, hours=15, minutes=40)
    CLOCK.set(thursday)
    session.add_block(
        {"id": "school", "title": "School", "kind": "locked", "category": "class",
         "start": "08:00", "duration_min": 390, "days": [0, 1, 2, 3, 4]}
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    yield made


def show(qapp: QApplication, window: NativeWindow, design: str, tab: str) -> QAbstractButton:
    """Put `design` on screen at `tab`, by a click on the tab's button, which keeps the keyboard."""
    window._layout = sanitize_layout({"main": design, "day": "one"})
    window._apply_appearance()
    window._on_week()
    button = window.findChild(QAbstractButton, f"view{tab.title()}")
    button.setFocus()
    button.click()
    wait_until(qapp, lambda: not window.session.busy)
    for _ in range(5):
        qapp.processEvents()
    return button


def hours(window: NativeWindow) -> HoursScroll:
    page = window.planner.currentWidget()
    shown = [scroll for scroll in page.findChildren(HoursScroll) if scroll.isVisible()]
    assert len(shown) == 1, f"{len(shown)} hours on screen"
    return shown[0]


def test_ctrl_and_equals_minus_and_zero_zoom_the_hours_showing_wherever_the_keyboard_is(
    qapp: QApplication, window: NativeWindow
) -> None:
    seen: dict[tuple[str, str], list[int]] = {}
    for design in DESIGNS:
        for tab in ("week", "day"):
            button = show(qapp, window, design, tab)
            assert QApplication.focusWidget() is button, f"{design} {tab}: the keyboard left the tab"
            scroll = hours(window)
            levels = []
            for press in PRESSES:
                QTest.keyClick(QApplication.focusWidget(), KEYS[press], Qt.KeyboardModifier.ControlModifier)
                levels.append(scroll.px)
            seen[(design, tab)] = levels
    assert seen == LEVELS


def test_with_the_hours_holding_the_keyboard_one_press_is_one_step(
    qapp: QApplication, window: NativeWindow
) -> None:
    seen: dict[tuple[str, str], list[int]] = {}
    for design in DESIGNS:
        for tab in ("week", "day"):
            show(qapp, window, design, tab)
            scroll = hours(window)
            scroll.canvas.setFocus()
            assert QApplication.focusWidget() is scroll.canvas
            levels = []
            for press in PRESSES:
                QTest.keyClick(scroll.canvas, KEYS[press], Qt.KeyboardModifier.ControlModifier)
                levels.append(scroll.px)
            seen[(design, tab)] = levels
    assert seen == LEVELS
