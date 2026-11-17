# ruff: noqa: F811
"""A notice after a drag names the day from its date. The clock is Thursday 5 November 2026, so a week
from Wednesday runs Wed 4 to Tue 10 and a week from Sunday runs Sun 1 to Sat 7. Column 2 is Friday 6
in the first and column 6 is Saturday 7 in the second (a Monday week would call them Wed and Sun)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from desktop.native import fields
from desktop.native.window import NativeWindow
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_drag import (
    answer_editors,
    create_on,
    drag,
    notice,
    qapp,  # noqa: F401
    session_of,
    settled,
    tray_chip,
    window,  # noqa: F401
)


def _open_week_from(qapp: QApplication, window: NativeWindow, first_day: str, iso: str) -> None:
    fields.save_week_starts_on(first_day)
    wait_until(qapp, lambda: window.session.week_start == iso and not window.session.busy)
    settled(qapp, window)


@pytest.mark.parametrize(
    ("first_day", "iso", "column", "named"),
    [("wednesday", "2026-11-04", 2, "Fri"), ("sunday", "2026-11-01", 6, "Sat")],
)
def test_the_added_and_the_placed_notice_name_the_day_from_its_date(
    qapp: QApplication,
    window: NativeWindow,
    monkeypatch: pytest.MonkeyPatch,
    first_day: str,
    iso: str,
    column: int,
    named: str,
) -> None:
    answer_editors(monkeypatch, "Club")
    _open_week_from(qapp, window, first_day, iso)
    hours = window.week_table.hours
    create_on(qapp, window, hours, column, "15:00-16:00", "Club")
    said = [notice(window)[1]]

    math = session_of(window, "math")["id"]
    hours.reveal(column, 17 * 60, 20 * 60)
    qapp.processEvents()
    drag(
        qapp,
        tray_chip(window, math),
        hours,
        tray_chip(window, math).mapToGlobal(QPoint(8, 8)),
        hours.point_for(column, 18 * 60),
    )
    wait_until(qapp, lambda: session_of(window, "math").get("start") == "18:00")
    settled(qapp, window)
    said.append(notice(window)[1])
    assert said == [
        f"Added Club on {named} 3:00 PM.",
        f"Placed Math worksheet on {named} 6:00 PM.",
    ]
