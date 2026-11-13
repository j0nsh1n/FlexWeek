"""A reminder comes five minutes before a planned session, and stops when that session is deleted."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import CLOCK
from desktop.native.controller import NativeSession
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.logic_support import essay, settled
from desktop.tests.window_support import qapp  # noqa: F401


def planned_session(qapp: QApplication, session: NativeSession) -> tuple[dict, datetime]:
    """The essay planned from Monday morning, so there is time left in the week whatever day the test
    runs; the planned session, and the moment two minutes before it starts."""
    monday = datetime.fromisoformat(session.week_start) + timedelta(hours=9)
    CLOCK.set(monday)
    session.add_homework(essay(session))
    session.save()
    settled(qapp, session)
    session.solve()
    settled(qapp, session)
    assert session.trace is not None
    placed = next(item for item in session.trace["placed"] if item["id"] == session.blocks[0]["id"])
    hours, minutes = placed["start"].split(":")
    starts = (
        datetime.fromisoformat(session.week_start)
        + timedelta(days=placed["days"][0], hours=int(hours), minutes=int(minutes))
    )
    return placed, starts - timedelta(minutes=2)


def test_a_planned_session_is_reminded_shortly_before_it_starts(
    qapp: QApplication, window: NativeWindow
) -> None:
    session = window.session
    _, shortly_before = planned_session(qapp, session)
    notices: list = []
    session.alerts.connect(lambda items: notices.extend(items))
    CLOCK.set(shortly_before)
    session.check_alerts()
    assert notices and {item["kind"] for item in notices} == {"reminder"}, "a planned session does remind"


def test_editing_the_week_stops_reminders_for_a_deleted_session(
    qapp: QApplication, window: NativeWindow
) -> None:
    session = window.session
    placed, shortly_before = planned_session(qapp, session)
    session.delete_block(placed["id"])
    assert session.trace is None
    notices: list = []
    session.alerts.connect(lambda items: notices.extend(items))
    CLOCK.set(shortly_before)
    session.check_alerts()
    settled(qapp, session)
    assert notices == []


def test_deleting_homework_in_a_week_from_wednesday_stops_its_reminder(
    qapp: QApplication, window: NativeWindow
) -> None:
    """A week shown from Wednesday reads today's reminders from the server's stored week and keeps them.
    Deleting the homework must read them again, or the deleted session still rings."""
    from desktop.native import fields
    from desktop.tests.waiting import wait_until

    session = window.session
    fields.save_week_starts_on("wednesday")
    wait_until(qapp, lambda: session.week_start == "2026-11-04" and not session.busy)
    placed, shortly_before = planned_session(qapp, session)
    notices: list = []
    session.alerts.connect(lambda items: notices.extend(items))
    CLOCK.set(shortly_before - timedelta(minutes=30))
    today_monday = (shortly_before.date() - timedelta(days=shortly_before.weekday())).isoformat()
    session.check_alerts()
    wait_until(qapp, lambda: session._reminder_week == today_monday)
    assert notices == []
    session.delete_homework(placed["assignment_id"])
    settled(qapp, session)
    CLOCK.set(shortly_before)
    session.check_alerts()
    settled(qapp, session)
    session.check_alerts()
    assert notices == []
