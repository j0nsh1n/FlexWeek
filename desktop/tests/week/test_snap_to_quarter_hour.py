"""A time made from where the pointer is lands on the nearest mark of the drag step the student chose (a
quarter hour on 15, every five minutes on 5): the free-time menu names that slot, a click opens New event on
it, and a block made by dragging starts on it."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QDialog

from desktop.native.widgets import BlockDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_clock import (
    busy_week,  # noqa: F401
    click,
    drag,
    menus,  # noqa: F401
    minute,
    right_click,
    saved,
    session_of,
    tray_chip,
)
from desktop.tests.window_support import qapp  # noqa: F401

SATURDAY, THURSDAY, FRIDAY = 5, 3, 4
STEPS = pytest.mark.parametrize("step", [5, 15])


def opened_editors(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """The start and end of each block editor that opens, which is then cancelled."""
    seen: list[tuple[str, str]] = []

    def look(dialog: BlockDialog) -> int:
        seen.append((dialog.start.time().toString("HH:mm"), dialog.end.time().toString("HH:mm")))
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(BlockDialog, "exec", look)
    return seen


@pytest.mark.parametrize("twenty_four", [True, False])
@pytest.mark.parametrize(
    ("step", "pointer", "slot", "twelve"),
    [
        (15, "17:05", "17:00", "5:00 PM"),
        (15, "17:20", "17:15", "5:15 PM"),
        (15, "17:25", "17:30", "5:30 PM"),
        (15, "16:57", "17:00", "5:00 PM"),
        (15, "17:40", "17:45", "5:45 PM"),
        (5, "17:05", "17:05", "5:05 PM"),
        (5, "17:20", "17:20", "5:20 PM"),
        (5, "17:25", "17:25", "5:25 PM"),
        (5, "16:55", "16:55", "4:55 PM"),
        (5, "17:40", "17:40", "5:40 PM"),
    ],
)
def test_a_right_click_on_free_time_names_the_nearest_mark_of_the_step(
    qapp: QApplication,
    busy_week: NativeWindow,
    menus: dict,
    step: int,
    pointer: str,
    slot: str,
    twelve: str,
    twenty_four: bool,
) -> None:
    window = busy_week
    window.session.preferences = {**(window.session.preferences or {}), "clock_24h": twenty_four}
    window._sync_chrome()
    window.hand.step = step
    hours = window.week_table.hours
    hours.reveal(SATURDAY, minute("16:00"), minute("18:30"))
    qapp.processEvents()
    right_click(hours, hours.point_for(SATURDAY, minute(pointer)))
    assert menus["shown"][-1][0] == f"Add fixed time at {slot if twenty_four else twelve}"


@pytest.mark.parametrize(
    ("step", "pointer", "slot"),
    [
        (15, "07:57", "08:00"),
        (15, "08:05", "08:00"),
        (15, "08:10", "08:15"),
        (15, "09:50", "09:45"),
        (5, "07:55", "07:55"),
        (5, "08:05", "08:05"),
        (5, "08:10", "08:10"),
        (5, "09:50", "09:50"),
    ],
)
def test_a_click_on_free_time_opens_new_event_on_the_nearest_mark_of_the_step(
    qapp: QApplication,
    busy_week: NativeWindow,
    monkeypatch: pytest.MonkeyPatch,
    step: int,
    pointer: str,
    slot: str,
) -> None:
    window = busy_week
    window.hand.step = step
    seen = opened_editors(monkeypatch)
    hours = window.week_table.hours
    hours.reveal(SATURDAY, minute("07:00"), minute("11:00"))
    qapp.processEvents()
    click(qapp, hours, hours.point_for(SATURDAY, minute(pointer)))
    assert [start for start, _end in seen] == [slot]


@pytest.mark.parametrize(
    ("step", "pointer", "slot"),
    [
        (15, "09:57", "10:00"),
        (15, "10:04", "10:00"),
        (15, "10:12", "10:15"),
        (5, "09:55", "09:55"),
        (5, "10:05", "10:05"),
        (5, "10:10", "10:10"),
    ],
)
def test_a_block_made_by_dragging_starts_on_the_nearest_mark_of_the_step(
    qapp: QApplication,
    busy_week: NativeWindow,
    monkeypatch: pytest.MonkeyPatch,
    step: int,
    pointer: str,
    slot: str,
) -> None:
    window = busy_week
    window.hand.step = step
    seen = opened_editors(monkeypatch)
    hours = window.week_table.hours
    hours.reveal(SATURDAY, minute("09:00"), minute("12:30"))
    qapp.processEvents()
    drag(
        qapp,
        hours,
        hours,
        hours.point_for(SATURDAY, minute(pointer)),
        hours.point_for(SATURDAY, minute("11:00")),
    )
    wait_until(qapp, lambda: bool(seen))
    assert seen == [(slot, "11:00")]


@STEPS
def test_a_homework_chip_dropped_on_a_line_lands_on_it(
    qapp: QApplication, busy_week: NativeWindow, step: int
) -> None:
    """A chip's time is the pointer's, rounded to the nearest step."""
    window = busy_week
    window.hand.step = step
    hours = window.week_table.hours
    math = session_of(window, "math")["id"]
    hours.reveal(FRIDAY, minute("09:00"), minute("12:00"))
    qapp.processEvents()
    chip = tray_chip(window, math)
    onto = hours.point_for(FRIDAY, minute("10:00")) + QPoint(0, -1)
    drag(qapp, chip, hours, chip.mapToGlobal(QPoint(8, 8)), onto)
    wait_until(qapp, lambda: session_of(window, "math").get("start") == "10:00")
    saved(qapp, window)
    assert session_of(window, "math")["days"] == [FRIDAY]


@STEPS
def test_a_block_carried_so_its_top_is_on_a_line_lands_on_it(
    qapp: QApplication, busy_week: NativeWindow, step: int
) -> None:
    """Held half an hour down the essay (19:00), and let go with that point on 20:30 a pixel short, its
    top is on 20:00."""
    window = busy_week
    window.hand.step = step
    hours = window.week_table.hours
    hours.reveal(THURSDAY, minute("18:00"), minute("22:00"))
    qapp.processEvents()
    drag(
        qapp,
        hours,
        hours,
        hours.point_for(THURSDAY, minute("19:30")),
        hours.point_for(FRIDAY, minute("20:30")) + QPoint(0, -1),
    )
    wait_until(qapp, lambda: session_of(window, "essay")["days"] == [FRIDAY])
    saved(qapp, window)
    assert session_of(window, "essay")["start"] == "20:00"
