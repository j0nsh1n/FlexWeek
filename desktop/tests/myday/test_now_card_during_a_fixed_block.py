# ruff: noqa: F811
"""Jonathan, 2026-11-09: while a fixed block such as Soccer or School is on, the Now card says what is on
and until when, then what comes next, with no Start button: "Soccer until 17:30" and "Next: History essay
at 18:45". Before, the card was gone, and its Start button with it.

Thursday 16:11 with Soccer 16:00-17:30 and the History essay at 18:45.
"""

from __future__ import annotations

import os
from datetime import timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from backend.tests.fake_clock import CLOCK  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_material_day import pref, root_bridge, seed_thursday  # noqa: E402
from desktop.tests.light_app import open_light  # noqa: E402, F401
from desktop.tests.material_support import named, pump, qml, show_material  # noqa: E402
from desktop.tests.sheets.support_material_settings import click_segment, open_settings, panel  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.window_support import qapp, settled  # noqa: E402, F401


@pytest.fixture()
def window(qapp: QApplication, open_light) -> NativeWindow:
    return seed_thursday(qapp, open_light((1280, 800)), hour=16, minute=11, soccer=True)


@pytest.mark.parametrize(("page", "scope"), [("myday", "myDay"), ("day", "day")])
def test_while_soccer_is_on_the_card_says_until_when_and_what_is_next_without_start(
    qapp: QApplication, window: NativeWindow, page: str, scope: str
) -> None:
    pref(window, clock_24h=True)
    root = show_material(qapp, window)
    bridge = root_bridge(root)
    bridge.showPage(page)
    pump(qapp)
    assert qml(root, scope + "NowTitle").property("visible") is True
    assert str(qml(root, scope + "NowTitle").property("text")) == "Soccer until 17:30"
    assert str(qml(root, scope + "NowLine").property("text")) == "Next: History essay at 18:45"
    assert qml(root, scope + "StartFocus").property("visible") is False


def test_after_soccer_the_free_time_card_has_its_start_button(qapp: QApplication, open_light) -> None:
    window = seed_thursday(qapp, open_light((1280, 800)), hour=17, minute=40, soccer=True)
    pref(window, clock_24h=True)
    root = show_material(qapp, window)
    root_bridge(root).showPage("myday")
    pump(qapp)
    assert str(qml(root, "myDayNowTitle").property("text")) == "Free for 1 h 5 min"
    assert qml(root, "myDayStartFocus").property("visible") is True


@pytest.mark.parametrize(("page", "scope"), [("myday", "myDay"), ("day", "day")])
def test_keyboard_focus_leaves_start_when_the_clock_moves_into_soccer(
    qapp: QApplication, open_light, page: str, scope: str
) -> None:
    """Start held the keyboard at 15:50; at 16:05 it hides, and focus must land on something shown."""
    window = seed_thursday(qapp, open_light((1280, 800)), hour=15, minute=50, soccer=True)
    pref(window, clock_24h=True)
    root = show_material(qapp, window)
    bridge = root_bridge(root)
    bridge.showPage(page)
    pump(qapp)
    start = qml(root, scope + "StartFocus")
    start.forceActiveFocus()
    pump(qapp)
    assert start.property("activeFocus") is True
    CLOCK.set(CLOCK.now() + timedelta(minutes=15))
    bridge.property(page).reload("light")
    pump(qapp)
    assert str(qml(root, scope + "NowTitle").property("text")) == "Soccer until 17:30"
    held = window._material_page._quick.quickWindow().activeFocusItem()
    assert start.property("activeFocus") is False
    assert held is not None and held.property("visible") is True, "keyboard focus is on nothing shown"


def test_a_focus_timer_during_soccer_keeps_its_card_and_button(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = show_material(qapp, window)
    bridge = root_bridge(root)
    focus = bridge.property("focus")
    try:
        bridge.property("myday").startFocus()
        pump(qapp)
        focus.hide()
        pump(qapp)
        bridge.showPage("myday")
        pump(qapp)
        start = qml(root, "myDayStartFocus")
        assert str(start.property("text")) == "Back to History essay"
        assert start.property("visible") is True
    finally:
        window.session.reset_focus()
        pump(qapp)


def test_the_settings_day_preview_hides_start_while_soccer_is_on(
    qapp: QApplication, window: NativeWindow
) -> None:
    pref(window, clock_24h=True)
    root = show_material(qapp, window)
    root_bridge(root).showPage("day")
    pump(qapp)
    root = open_settings(qapp, window)
    panel(window).openAdvanced()
    pump(qapp, 10)
    click_segment(qapp, window, named(root, "previewView")[0], "Day")
    wait_until(qapp, lambda: bool(named(root, "settingsPreviewDay")))
    pump(qapp, 20)
    preview = named(root, "settingsPreviewDay")[0]
    titles = [str(t.property("text")) for t in named(preview, "dayNowTitle")]
    assert titles == ["Soccer until 17:30"]
    assert [s.property("visible") for s in named(preview, "dayStartFocus")] == [False]
