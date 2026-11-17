"""Undo and Redo of a session length, in a week that starts on any day, before the server's read lands.

Clock Thursday 19 Nov 2026 15:40. A 60 min homework due Tuesday 24 at 21:00 has one pinned session today at
18:00. Cut to 30 min the homework still needs 30; lengthened to 60 it needs 0. Undo puts the 30 back, so 30
are needed again; Redo puts the 60 back, so 0. Each must hold while the app's re-read of the numbers fails,
is held, or lands: the open week's own change is counted once, never twice, in a week from Monday, Wednesday
or Friday alike (the latter two are stored as two Monday weeks)."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from backend.tests.fake_clock import FakeClock
from desktop.native.client import ApiError
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.logic_support import settled
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

THURSDAY = datetime(2026, 11, 19, 15, 40)


def _hold(session, monkeypatch, fail: bool) -> None:
    real = session.client.request
    held: list[str] = []

    def request(method, path, payload, on_success, on_error):
        if method == "GET" and path.startswith("/api/assignments"):
            if fail:
                on_error(ApiError(0, "down"))
            else:
                held.append(path)
            return None
        return real(method, path, payload, on_success, on_error)

    monkeypatch.setattr(session.client, "request", request)


def _saved(qapp, session) -> None:
    wait_until(
        qapp, lambda: not session.busy and session.pending_save is None and not session.dirty, what="saved"
    )
    settled(qapp, session)


def _needed(session) -> int:
    return {i["assignment_id"]: i["minutes"] for i in session.homework_time_needed()}.get("essay", 0)


def _lengthen(qapp, session, minutes: int) -> None:
    block = next(b for b in session.blocks if b.get("assignment_id") == "essay")
    block.update(duration_min=minutes)
    session._touch("lengthening")
    session.save()
    _saved(qapp, session)
    wait_until(qapp, lambda: session.assignments["essay"].get("planned_min") == minutes, what="read")
    settled(qapp, session)


@pytest.mark.parametrize("first_weekday", [0, 2, 4], ids=["monday", "wednesday", "friday"])
@pytest.mark.parametrize("reads", ["fail", "held", "land"])
def test_undo_and_redo_of_a_length_count_the_open_week_once(
    qapp, open_light, clock: FakeClock, monkeypatch, first_weekday, reads
) -> None:
    clock.set(THURSDAY)
    session = open_light().session
    session.follow_first_weekday(first_weekday)
    today = THURSDAY.date()
    first = today - timedelta(days=(today.weekday() - first_weekday) % 7)
    wait_until(qapp, lambda: session.week_start == first.isoformat() and not session.busy, what="week")
    settled(qapp, session)
    session.add_homework(
        {
            "id": "essay",
            "title": "History essay",
            "due": "2026-11-24T21:00",
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.save()
    _saved(qapp, session)
    block = next(b for b in session.blocks if b.get("assignment_id") == "essay")
    block.update(duration_min=30, pinned=True, start="18:00", days=[(today - first).days])
    session._touch("placing")
    session.save()
    _saved(qapp, session)
    wait_until(qapp, lambda: session.assignments["essay"].get("planned_min") == 30, what="read 30")
    settled(qapp, session)
    assert _needed(session) == 30
    _lengthen(qapp, session, 60)
    assert _needed(session) == 0

    if reads != "land":
        _hold(session, monkeypatch, reads == "fail")
    for travel, length, needed in ((session.undo, 30, 30), (session.redo, 60, 0)):
        travel()
        _saved(qapp, session)
        if reads == "land":
            wait_until(
                qapp,
                lambda length=length: session.assignments["essay"].get("planned_min") == length,
                what="read",
            )
            settled(qapp, session)
        lengths = [b["duration_min"] for b in session.blocks if b.get("assignment_id") == "essay"]
        assert lengths == [length]
        assert _needed(session) == needed
