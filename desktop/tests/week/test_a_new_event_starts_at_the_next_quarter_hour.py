"""A new event, Choose a time and Running late start at a time that is still ahead: the next quarter
hour, rounded up, never one that has passed."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialog

from desktop.native.hours.geometry import next_slot
from desktop.native.widgets import BlockDialog, ChooseTimeDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.week.support_typing import (
    FRIDAY,
    MONDAY,
    SUNDAY,
    THURSDAY,
    hold_clock,
    session_of,
    settled,
    week_window,  # noqa: F401
)
from desktop.tests.window_support import qapp  # noqa: F401


@pytest.mark.parametrize(
    ("now", "ahead", "slot"),
    [
        (0, 0, 0),
        (1, 0, 15),
        (15, 0, 15),
        (16 * 60 + 7, 0, 16 * 60 + 15),
        (23 * 60 + 33, 0, 23 * 60 + 45),
        (23 * 60 + 45, 0, 23 * 60 + 45),
        (23 * 60 + 46, 1, 0),
        (23 * 60 + 59, 1, 0),
    ],
)
def test_the_next_slot_is_the_next_quarter_hour_or_the_first_of_tomorrow(
    now: int, ahead: int, slot: int
) -> None:
    assert next_slot(now) == (ahead, slot)


def test_the_next_slot_keeps_to_the_hours_it_is_given() -> None:
    assert next_slot(3 * 60 + 10, first=6 * 60, last=23 * 60) == (0, 6 * 60), "not before the first"
    assert next_slot(23 * 60 + 1, first=6 * 60, last=23 * 60) == (1, 6 * 60), "none left: tomorrow's first"
    assert next_slot(22 * 60 + 50, first=6 * 60, last=23 * 60) == (0, 23 * 60)


def opened_event(window: NativeWindow, monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    seen: list[tuple] = []

    def look(dialog: BlockDialog) -> int:
        days = [day for day, box in enumerate(dialog.days) if box.isChecked()]
        seen.append((days, dialog.start.time().toString("HH:mm")))
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(BlockDialog, "exec", look)
    window._add_fixed()
    return seen


@pytest.mark.parametrize(
    ("day", "now", "opens"),
    [
        (THURSDAY, "23:33", ([THURSDAY], "23:45")),
        (THURSDAY, "23:23", ([THURSDAY], "23:30")),
        (THURSDAY, "16:00", ([THURSDAY], "16:00")),
        (THURSDAY, "16:00:40", ([THURSDAY], "16:00")),
        (THURSDAY, "16:01", ([THURSDAY], "16:15")),
        (THURSDAY, "00:05", ([THURSDAY], "00:15")),
        (THURSDAY, "23:50", ([FRIDAY], "00:00")),
    ],
)
def test_a_new_event_opens_at_the_next_free_quarter_hour(
    week_window: NativeWindow, monkeypatch: pytest.MonkeyPatch, day: int, now: str, opens: tuple
) -> None:
    hold_clock(week_window, day, now)
    assert opened_event(week_window, monkeypatch) == [opens]


def test_a_new_event_on_a_week_that_is_not_this_one_keeps_its_usual_start(
    qapp: QApplication, week_window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    week_window.session.load_week(
        (datetime.fromisoformat(week_window.session.week_start) + timedelta(days=7)).date().isoformat()
    )
    settled(qapp, week_window)
    assert opened_event(week_window, monkeypatch) == [([MONDAY], "16:00")]


def test_a_new_event_late_on_sunday_opens_on_a_start_that_exists(
    week_window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tomorrow is another week, which this one cannot hold, so the usual start is kept."""
    hold_clock(week_window, SUNDAY, "23:50")
    assert opened_event(week_window, monkeypatch) == [([MONDAY], "16:00")]


def choose_time_opens(window: NativeWindow, monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, str]]:
    seen: list[tuple[int, str]] = []

    def look(dialog: ChooseTimeDialog) -> int:
        seen.append((int(dialog.day.currentData()), dialog.start.time().toString("HH:mm")))
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(ChooseTimeDialog, "exec", look)
    window._choose_time(session_of(window, "math")["assignment_id"])
    return seen


@pytest.mark.parametrize(
    ("now", "opens"),
    [
        ("19:40", (THURSDAY, "19:45")),
        ("16:00", (THURSDAY, "16:00")),
        ("16:07", (THURSDAY, "16:15")),
        ("22:50", (THURSDAY, "23:00")),
        ("03:10", (THURSDAY, "06:00")),
    ],
)
def test_choose_a_time_opens_at_the_next_quarter_hour_today(
    week_window: NativeWindow, monkeypatch: pytest.MonkeyPatch, now: str, opens: tuple
) -> None:
    hold_clock(week_window, THURSDAY, now)
    assert choose_time_opens(week_window, monkeypatch) == [opens]


def test_choose_a_time_late_in_the_evening_opens_on_tomorrow_morning(
    week_window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A one hour session cannot start after 23:00, so at 23:33 none is left today. The box starts at
    06:00, so that is tomorrow's first."""
    hold_clock(week_window, THURSDAY, "23:33")
    assert choose_time_opens(week_window, monkeypatch) == [(FRIDAY, "06:00")]
