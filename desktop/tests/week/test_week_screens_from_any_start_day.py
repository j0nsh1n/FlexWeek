# ruff: noqa: F811
"""The Week screen shows the seven days from the chosen first day, in both styles. The clock is
Thursday 5 November 2026: from Wednesday the week runs Wednesday 4 to Tuesday 10 November, from Sunday
Sunday 1 to Saturday 7 November. Day names are read off the calendar, never off a column's place."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native import fields
from desktop.native.window import NativeWindow
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_material import (
    _bridge,
    _click,
    _named,
    _pump,
    _qml,
    _reset,
    material_window,  # noqa: F401
)
from desktop.tests.window_support import qapp, settled  # noqa: F401

WEDNESDAY_WEEK = ["Wed 4", "Thu 5", "Fri 6", "Sat 7", "Sun 8", "Mon 9", "Tue 10"]


def _headers(root) -> list[str]:
    return [str(item.property("text")) for item in _named(root, "dayHeader")]


def _start_on(qapp: QApplication, window: NativeWindow, start: str, first: str) -> None:
    fields.save_week_starts_on(start)
    wait_until(qapp, lambda: window.session.week_start == first and not window.session.busy)
    settled(qapp, window)
    _pump(qapp)


def test_material_week_headers_run_from_the_chosen_day(qapp, window) -> None:
    root = _reset(window, qapp)
    _start_on(qapp, window, "wednesday", "2026-11-04")
    wait_until(qapp, lambda: _headers(root) == WEDNESDAY_WEEK, what="the headers to run from Wednesday")
    _start_on(qapp, window, "sunday", "2026-11-01")
    wait_until(
        qapp,
        lambda: _headers(root) == ["Sun 1", "Mon 2", "Tue 3", "Wed 4", "Thu 5", "Fri 6", "Sat 7"],
        what="the headers to run from Sunday",
    )


def test_material_hides_saturday_and_sunday_wherever_they_fall(qapp, window) -> None:
    root = _reset(window, qapp)
    _start_on(qapp, window, "wednesday", "2026-11-04")
    # Club on Monday 9 November, shown day 5, after the hidden weekend.
    window.session.add_block(
        {"id": "club", "title": "Club", "kind": "locked", "start": "16:00", "duration_min": 60, "days": [5]}
    )
    window.session.save()
    settled(qapp, window)
    _click(window, _qml(root, "toggleWeekends"))
    settled(qapp, window)
    _pump(qapp)
    wait_until(qapp, lambda: _headers(root) == ["Wed 4", "Thu 5", "Fri 6", "Mon 9", "Tue 10"])
    titles = [str(item.property("title")) for item in _named(root, "weekBlock")]
    assert titles.count("Club") == 1


def test_material_next_today_and_go_to_date_open_weeks_from_the_chosen_day(qapp, window) -> None:
    root = _reset(window, qapp)
    _start_on(qapp, window, "wednesday", "2026-11-04")
    _click(window, _qml(root, "weekNext"))
    wait_until(qapp, lambda: window.session.week_start == "2026-11-11" and not window.session.busy)
    _pump(qapp)
    wait_until(qapp, lambda: _headers(root)[0] == "Wed 11")
    _click(window, _qml(root, "weekToday"))
    wait_until(qapp, lambda: window.session.week_start == "2026-11-04" and not window.session.busy)
    # Tuesday 17 November is in the week from Wednesday 11.
    _bridge(window).week.goToDate("2026-11-17")
    wait_until(qapp, lambda: window.session.week_start == "2026-11-11" and not window.session.busy)
    _click(window, _qml(root, "weekPrevious"))
    wait_until(qapp, lambda: window.session.week_start == "2026-11-04" and not window.session.busy)
