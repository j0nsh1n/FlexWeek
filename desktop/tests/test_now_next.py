"""The line over Today's app's week that says what is on now and what is next. Its countdown moves with
the clock, not only while a focus timer ticks."""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QStandardPaths
    from PySide6.QtWidgets import QAbstractButton, QApplication

    from backend.tests.fake_clock import FakeClock
    from desktop.native.window import NativeWindow
    from desktop.tests.light_app import open_light  # noqa: F401
    from desktop.tests.waiting import wait_until


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-now-next-test"])


@pytest.fixture()
def window(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> tuple[NativeWindow, FakeClock]:
    """Today's app's Week, signed in, with Dinner every day at 18:00 and the clock held at Thursday
    15:40. A test moves the clock on."""
    made = open_light((1280, 860))
    session = made.session
    clock.set(datetime.fromisoformat(session.week_start) + timedelta(days=3, hours=15, minutes=40))
    session.add_block(
        {"id": "dinner", "title": "Dinner", "kind": "locked", "category": "meals",
         "start": "18:00", "duration_min": 30, "days": [0, 1, 2, 3, 4, 5, 6]}
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    made.findChild(QAbstractButton, "viewWeek").click()
    # The refreshes a save starts redraw the week when they land; none may be left to land
    # during the test and redraw the line for it.
    wait_until(qapp, lambda: not session.busy and not any(session.client._replies.values()))
    return made, clock


@pytest.mark.parametrize("twenty_four", [True, False])
def test_the_next_and_now_countdowns_move_with_the_minute_without_a_focus_timer(
    qapp: QApplication, window: tuple[NativeWindow, FakeClock], twenty_four: bool
) -> None:
    made, clock = window
    made.session.preferences = {**(made.session.preferences or {}), "clock_24h": twenty_four}
    made._sync_chrome()
    dinner, half_past = ("18:00", "18:30") if twenty_four else ("6:00 PM", "6:30 PM")
    # On the week, what is next is the rail's card: "Next", what, and when.
    card = made.rail.next

    def said() -> tuple[str, str, str]:
        return card.label.text(), card.title.text(), card.when.text()

    line = card
    assert made.session.focus is None
    assert card.isVisible()
    assert said() == ("Next", "Dinner", f"{dinner} · in 2 h 20 min")
    # The window looks at the clock on its own timer; here it looks every 20 ms, not every 20 s.
    made._layout_tick.setInterval(20)
    clock.move(minutes=1)
    expected = ("Next", "Dinner", f"{dinner} · in 2 h 19 min")
    wait_until(qapp, lambda: said() == expected, what=lambda: f"it said {said()}")
    clock.move(hours=2, minutes=29)
    expected = ("Now", "Dinner", f"until {half_past} · 20 min left")
    wait_until(qapp, lambda: said() == expected, what=lambda: f"it said {said()}")
    clock.move(minutes=1)
    expected = ("Now", "Dinner", f"until {half_past} · 19 min left")
    wait_until(qapp, lambda: said() == expected, what=lambda: f"it said {said()}")
    clock.move(minutes=19)
    wait_until(qapp, lambda: not line.isVisible(), what="nothing now or next today: the card takes no room")
