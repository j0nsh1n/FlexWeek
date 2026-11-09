# ruff: noqa: F811
"""Jonathan, 2026-11-09: while a fixed block such as Soccer or School is on, the Now card says what is on
and until when, then what comes next, with no Start button: "Soccer until 17:30" and "Next: History essay
at 18:45". Before, the card was gone, and its Start button with it.

Thursday 16:11 with Soccer 16:00-17:30 and the History essay at 18:45.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_material_day import pref, root_bridge, seed_thursday  # noqa: E402
from desktop.tests.light_app import open_light  # noqa: E402, F401
from desktop.tests.material_support import pump, qml, show_material  # noqa: E402
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
