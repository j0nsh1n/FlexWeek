# ruff: noqa: F811
"""What the Material week says: the blocks and homework from the session, the clock in the user's
12 or 24 hour words, the day headers, and the clock words and now line that follow the time.

Titles, counts and words are the account's data. How big or where anything is drawn is a picture
(desktop/tests/pictures/_week_g11.py).
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from backend.tests.fake_clock import FakeClock  # noqa: E402
from desktop.native.calendar import sunday_due  # noqa: E402
from desktop.native.weekmodel import clock_label  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_material_window import (  # noqa: E402, F401
    material_window,
    qapp,
    settle,
)
from desktop.tests.material_support import named, pump, qml, repeater_texts, show_material  # noqa: E402


@pytest.mark.parametrize(("twenty_four", "clock_words"), [(False, "7:00 PM"), (True, "19:00")])
def test_the_material_week_lists_the_blocks_the_headers_and_the_open_homework(
    qapp: QApplication, material_window: NativeWindow, twenty_four: bool, clock_words: str
) -> None:
    session = material_window.session
    session.add_homework(
        {
            "id": "worksheet",
            "title": "Math worksheet",
            "due": sunday_due(session.week_start),
            "estimate_min": 30,
            "revision": 0,
        }
    )
    session.save()
    settle(qapp, material_window)
    session.preferences = {**(session.preferences or {}), "clock_24h": twenty_four}

    root = show_material(qapp, material_window)

    assert qml(root, "materialClock").property("text") == clock_words
    titles = repeater_texts(root, "weekBlocks", "title")
    assert "School" in titles, titles
    assert "History essay" in titles, titles
    start = date.fromisoformat(session.week_start)
    assert f"Thu {(start + timedelta(days=3)).day}" in repeater_texts(root, "dayHeaders", "dayHeader")
    assert qml(root, "nowLine").property("visible") is True
    # The essay is planned, so only the worksheet is left in the drawer.
    assert qml(root, "homeworkCount").property("text") == "1"
    assert "Math worksheet" in repeater_texts(root, "homeworkRows", "homeworkTitle")


def test_the_material_clock_words_and_now_line_follow_the_time(
    qapp: QApplication, material_window: NativeWindow, clock: FakeClock
) -> None:
    root = show_material(qapp, material_window)
    before = int(qml(root, "nowLine").property("y"))
    assert qml(root, "materialClock").property("text") == clock_label(19 * 60)

    clock.move(hours=1)
    material_window._layout_tick.timeout.emit()
    pump(qapp)

    assert qml(root, "materialClock").property("text") == clock_label(20 * 60)
    # The line sits at its minute of the day from the top of the hours: an hour later is 20/19 as far.
    after = int(qml(root, "nowLine").property("y"))
    assert after > before
    assert abs(after * 19 - before * 20) < 20


def test_the_material_week_comes_from_the_session(qapp: QApplication, material_window: NativeWindow) -> None:
    root = show_material(qapp, material_window)
    assert named(root, "weekBlock")

    class Empty:
        occurrences: tuple = ()

        def on_day(self, day: int) -> tuple:
            return ()

    material_window.session.built_week = lambda: Empty()
    material_window._material_page.bridge.refresh()
    pump(qapp)
    assert named(root, "weekBlock") == []
