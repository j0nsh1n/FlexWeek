"""Homework placed by Plan and saved is still where it was after the student signs out and in again."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtWidgets import QApplication, QPushButton

from backend.tests.fake_clock import FakeClock
from desktop.native.controller import NativeSession
from desktop.native.window import NativeWindow
from desktop.server import LocalServer
from desktop.tests.e2e.account_sessions import (  # noqa: F401
    HELD,
    PASSWORD,
    server,
    signed_in,
    soccer,
    table_text,
)
from desktop.tests.logic_support import past_setup
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

MONDAY_MORNING = datetime(2026, 11, 2, 0, 0)


def two_assignments(session: NativeSession) -> None:
    session.add_block(soccer())
    monday = date.fromisoformat(session.week_start)
    session.add_homework(
        {
            "id": "math",
            "title": "Math worksheet",
            "due": (monday + timedelta(days=4)).isoformat() + "T21:00",
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.add_homework(
        {
            "id": "english",
            "title": "English essay",
            "due": (monday + timedelta(days=5)).isoformat() + "T21:00",
            "estimate_min": 60,
            "revision": 0,
        }
    )


def work_starts(session: NativeSession) -> dict[str, str | None]:
    return {
        item["title"]: item.get("start")
        for item in session.blocks
        if item.get("kind") == "flexible" and item.get("assignment_id")
    }


def test_accepted_homework_placements_survive_save_and_a_new_session(
    qapp: QApplication, server: LocalServer, clock: FakeClock
) -> None:
    # Plan puts nothing before now, so the week is still ahead of the clock.
    clock.set(MONDAY_MORNING)
    session = signed_in(qapp, server.origin, "alice", create=True)
    two_assignments(session)
    session.save()
    wait_until(qapp, lambda: session.revision >= 1 and not session.busy and not session.dirty)
    session.solve()
    wait_until(qapp, lambda: session.trace is not None and not session.busy and not session.dirty)
    starts = work_starts(session)
    assert starts["Math worksheet"]
    assert starts["English essay"]
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    session.client.reset()

    again = signed_in(qapp, server.origin, "alice", create=False)
    wait_until(qapp, lambda: not again.busy and len(again.assignments) >= 2)
    later = work_starts(again)
    assert later == starts
    assert again.trace is None


def test_an_accepted_plan_is_on_the_grid_after_closing_and_signing_in(
    qapp: QApplication, server: LocalServer, clock: FakeClock
) -> None:
    clock.set(MONDAY_MORNING)
    first = NativeWindow(server.origin)
    HELD.append(first)
    first.show()
    first.username.setText("alice")
    first.password.setText(PASSWORD)
    first.findChild(QPushButton, "createAccount").click()
    wait_until(qapp, lambda: first._stack.currentWidget().objectName() == "recoveryPage")
    first.recovery_ack.setChecked(True)
    first.recovery_continue.click()
    past_setup(qapp, first)
    two_assignments(first.session)
    first.session.save()
    wait_until(qapp, lambda: not first.session.busy and not first.session.dirty)
    first.findChild(QPushButton, "solveButton").click()
    wait_until(
        qapp, lambda: first.session.trace is not None and not first.session.busy and not first.session.dirty
    )
    starts = work_starts(first.session)
    assert starts["Math worksheet"] and starts["English essay"]
    first.session.save()
    wait_until(qapp, lambda: not first.session.busy and not first.session.dirty)
    grid = table_text(first)
    assert "Math worksheet" in grid
    assert "English essay" in grid
    first.session.client.reset()
    first.hide()

    second = NativeWindow(server.origin)
    HELD.append(second)
    second.show()
    second.username.setText("alice")
    second.password.setText(PASSWORD)
    second.findChild(QPushButton, "signIn").click()
    wait_until(
        qapp,
        lambda: (
            second._stack.currentWidget().objectName() == "weekPage"
            and not second.session.busy
            and len(second.session.assignments) >= 2
        ),
    )
    later = work_starts(second.session)
    assert later == starts
    shown = table_text(second)
    assert "Math worksheet" in shown
    assert "English essay" in shown
