"""Plan is asked once at a time, and says in words when it or a save cannot reach FlexWeek."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton

from desktop.native.window import NativeWindow
from desktop.tests.logic_support import fail_once
from desktop.tests.sheets.support_plan import held_solves, settled, window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

PLAN_UNREACHABLE = "Can't reach FlexWeek, so nothing was planned. Try again."
SAVE_UNREACHABLE = "Not saved: FlexWeek can't be reached. Your changes are still here. Choose Retry save."


def test_twelve_fast_clicks_on_plan_make_one_plan(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    sent, waiting = held_solves(window)
    plan = window.findChild(QPushButton, "solveButton")
    said: list[str] = []
    window.session.status.connect(said.append)
    for _ in range(12):
        plan.click()
        qapp.processEvents()
    assert not plan.isEnabled(), "disabled from the first click, not after the busy look's delay"
    assert len(sent) == 1
    assert said.count("Planning…") == 1
    waiting[0]()
    settled(qapp, window)
    assert plan.isEnabled(), "back once the result is in"
    assert len(sent) == 1


def test_plan_asked_for_in_other_ways_while_one_is_running_is_ignored(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    sent, waiting = held_solves(window)
    window.session.solve()
    for _ in range(11):
        window.session.solve()
        window.session.solve(everything=True)
    assert len(sent) == 1
    waiting[0]()
    settled(qapp, window)
    assert len(sent) == 1


def test_plan_when_flexweek_is_unreachable_says_nothing_was_planned(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    fail_once(window.session, "POST", "/api/solve", 0)
    window.session.solve()
    wait_until(qapp, lambda: not window.session.busy)
    assert window.session.message == PLAN_UNREACHABLE


def test_save_when_flexweek_is_unreachable_says_changes_are_kept(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    session = window.session
    session.blocks = [
        *session.blocks,
        {
            "id": "club",
            "title": "Club",
            "kind": "locked",
            "category": "extra",
            "start": "16:00",
            "duration_min": 60,
            "days": [3],
        },
    ]
    session.dirty = True
    fail_once(session, "POST", "/api/changes", 0)
    said: list[str] = []
    session.status.connect(said.append)
    session.save()
    # The autosave retry may already have saved by the time a busy test looks, so this reads what the
    # failed save said when it said it, not the latest line.
    wait_until(qapp, lambda: SAVE_UNREACHABLE in said)
