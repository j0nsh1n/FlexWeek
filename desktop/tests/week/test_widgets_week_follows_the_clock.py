# ruff: noqa: F811
"""Today's app (Widgets) notices time passing by itself. The clock is Tuesday 3 November 2026 in the
week of Monday 2 November; the essay has one hour planned on Tuesday 16:00 to 17:00. Nothing is
pressed: only the window's own timer fires after the clock has moved."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

import pytest
from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import FakeClock
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.planner.planning_week import due_on
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


@pytest.fixture()
def planned(qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock) -> NativeWindow:
    clock.set(datetime(2026, 11, 3, 15, 0))
    window = open_light()
    session = window.session
    session.add_homework(
        {
            "id": "essay",
            "title": "History essay",
            "due": due_on(session, 5, "23:59"),
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and session.pending_save is None)
    work = next(item for item in session.blocks if item.get("assignment_id") == "essay")
    work.update({"start": "16:00", "days": [1], "duration_min": 60})
    session.add_block(work)
    session.save()
    wait_until(qapp, lambda: not session.busy and session.pending_save is None)
    window._fill_classic()
    return window


def _marked_today(window: NativeWindow) -> list[int]:
    return [day for day in range(7) if window.week_table._name_labels[day].property("today")]


def test_the_rail_stops_saying_everything_has_a_time_once_a_session_has_passed_unfinished(
    planned: NativeWindow, clock: FakeClock
) -> None:
    rail = planned.rail.none_waiting
    assert rail.text() == "Everything has a time."
    clock.set(datetime(2026, 11, 3, 18, 0))
    planned._layout_tick.timeout.emit()
    assert rail.text() == "History essay · 1 h left"


def test_the_header_marks_the_new_day_once_midnight_has_passed(
    planned: NativeWindow, clock: FakeClock
) -> None:
    assert _marked_today(planned) == [1]
    clock.set(datetime(2026, 11, 4, 9, 0))
    planned._layout_tick.timeout.emit()
    assert _marked_today(planned) == [2]
