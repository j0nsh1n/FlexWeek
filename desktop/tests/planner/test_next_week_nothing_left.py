"""Thursday 15:40, all three homework planned later this week ("Everything has a time"), Next week pressed:
nothing is left and nothing needs a time. Each homework's 60 minutes sit in a session whose time is still
ahead of now, and a session in any week holds its time while its time is ahead (spec.md)."""

# ruff: noqa: F811
from __future__ import annotations

from datetime import date, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.week.support_material import chips, seeded
from desktop.tests.window_support import qapp, settled, wait_until  # noqa: F401

FRIDAY = 4


def _plan(qapp: QApplication, window: NativeWindow) -> None:
    window.findChild(QPushButton, "solveButton").click()
    wait_until(qapp, lambda: not window.session.planning and not window.session.busy)
    settled(qapp, window)


def test_next_week_lists_nothing_left_and_plan_has_nothing_to_place(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    seeded(qapp, window)
    session = window.session
    # The seed pins Chem on Monday, which is over; Friday keeps every session ahead of now.
    chem = next(item for item in session.blocks if item.get("assignment_id") == "chem")
    chem.update(start="20:00", days=[FRIDAY])
    session._touch()
    session.save()
    settled(qapp, window)
    _plan(qapp, window)
    assert session.homework_time_needed() == []

    here = date.fromisoformat(session.week_start)
    window.next_nav.click()
    settled(qapp, window)
    wait_until(
        qapp,
        lambda: session.week_start == (here + timedelta(days=7)).isoformat()
        and all("planned_min" in item for item in session.assignments.values()),
    )
    settled(qapp, window)

    assert session.homework_time_needed() == []
    assert window.rail.waiting_count.text() == ""
    assert [chip.accessibleName() for chip in chips(window)] == []
    assert "still needs time" not in window.solve_button.accessibleName()
    _plan(qapp, window)
    assert "still needs a time" not in session.message, session.message
    assert session.homework_time_needed() == []
