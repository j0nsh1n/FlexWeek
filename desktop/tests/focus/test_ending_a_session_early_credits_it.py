"""Ending a focus session early keeps the minutes already worked, as the End question promises ("It counts
toward the homework."). Held clock: Thursday 5 November 2026 in the week of Monday 2 November. The essay
is 60 minutes, planned Thursday 19:00 to 20:00; the student focuses on it from 19:00."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialog

from backend.tests.fake_clock import FakeClock
from desktop.native.controller import NativeSession
from desktop.native.widgets import ConfirmSheet
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.material_support import pump, show_material
from desktop.tests.planner.planning_week import due_on
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

SEVEN_PM = datetime(2026, 11, 5, 19, 0)


def _settle(qapp: QApplication, session: NativeSession) -> None:
    wait_until(qapp, lambda: not session.busy and session.pending_save is None)
    qapp.processEvents()


def _essay_at_seven(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> tuple[NativeWindow, dict]:
    clock.set(SEVEN_PM)
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
    _settle(qapp, session)
    work = next(item for item in session.blocks if item.get("assignment_id") == "essay")
    work.update({"start": "19:00", "days": [3], "duration_min": 60})
    session.add_block(work)
    session.save()
    _settle(qapp, session)
    return window, next(item for item in session.blocks if item["id"] == work["id"])


def _end_on_widgets(window: NativeWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    """Finish, then End session."""

    def run(sheet: ConfirmSheet) -> int:
        sheet.buttons["yes"].click()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(ConfirmSheet, "exec", run)
    window._stop_focus()


def _focus_minutes(session: NativeSession) -> int:
    return int(session.assignments["essay"].get("focus_minutes") or 0)


def test_ending_after_25_minutes_keeps_them_and_replan_asks_for_the_rest(
    qapp: QApplication,
    open_light: Callable[..., NativeWindow],
    clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """60 - 25 = 35 min still need a time. The planner places whole quarter hours, so Replan all places 30
    and 5 are still needed."""
    window, work = _essay_at_seven(qapp, open_light, clock)
    session = window.session
    assert session.start_focus(work["id"], 3) is True
    clock.move(minutes=25)
    _end_on_widgets(window, monkeypatch)
    _settle(qapp, session)
    assert session.focus is None
    assert _focus_minutes(session) == 25
    assert session.assignments["essay"].get("completed") is not True
    clock.set(datetime(2026, 11, 5, 20, 1))
    assert [item["minutes"] for item in session.homework_time_needed()] == [35]
    assert session.missed_block_ids() == frozenset({work["id"]})
    session.solve(everything=True)
    _settle(qapp, session)
    placed = [
        item["duration_min"]
        for item in session.blocks
        if item.get("assignment_id") == "essay" and item.get("start")
    ]
    assert placed == [30]
    assert [item["minutes"] for item in session.homework_time_needed()] == [5]


def test_ending_on_the_material_screen_keeps_the_minutes_too(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    window, work = _essay_at_seven(qapp, open_light, clock)
    session = window.session
    assert session.start_focus(work["id"], 3) is True
    show_material(qapp, window)
    window._open_focus_screen()
    pump(qapp)
    clock.move(minutes=25)
    window._material_page.bridge.focus.confirmEnd()
    pump(qapp)
    _settle(qapp, session)
    assert session.focus is None
    assert _focus_minutes(session) == 25


def test_ending_early_does_not_finish_the_session_or_the_homework(
    qapp: QApplication,
    open_light: Callable[..., NativeWindow],
    clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, work = _essay_at_seven(qapp, open_light, clock)
    session = window.session
    session.preferences = {**session.preferences, "focus_auto_complete": True}
    session.material_owns = lambda: True
    assert session.start_focus(work["id"], 3) is True
    clock.move(minutes=25)
    _end_on_widgets(window, monkeypatch)
    _settle(qapp, session)
    assert _focus_minutes(session) == 25
    block = next(item for item in session.blocks if item["id"] == work["id"])
    assert not block.get("completed")
    assert session.assignments["essay"].get("completed") is not True


def test_ending_at_zero_minutes_credits_nothing(
    qapp: QApplication,
    open_light: Callable[..., NativeWindow],
    clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, work = _essay_at_seven(qapp, open_light, clock)
    session = window.session
    assert session.start_focus(work["id"], 3) is True
    _end_on_widgets(window, monkeypatch)
    _settle(qapp, session)
    assert session.focus is None
    assert _focus_minutes(session) == 0


def test_ending_during_a_break_credits_nothing_more(
    qapp: QApplication,
    open_light: Callable[..., NativeWindow],
    clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A block's work phase ends in a break; the 30 minutes were credited when it ran out, and End in the
    break adds nothing."""
    window, work = _essay_at_seven(qapp, open_light, clock)
    session = window.session
    assert session.start_focus(work["id"], 3) is True
    clock.move(minutes=30)
    session.tick_focus()
    _settle(qapp, session)
    wait_until(qapp, lambda: _focus_minutes(session) == 30)
    clock.move(minutes=2)
    session.focus["phase"] = "break"
    _end_on_widgets(window, monkeypatch)
    _settle(qapp, session)
    assert session.focus is None
    assert _focus_minutes(session) == 30


def test_a_session_that_ran_out_is_credited_once_when_end_is_pressed_after(
    qapp: QApplication,
    open_light: Callable[..., NativeWindow],
    clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, work = _essay_at_seven(qapp, open_light, clock)
    session = window.session
    assert session.start_focus(work["id"], 3) is True
    clock.move(minutes=30)
    session.tick_focus()
    _settle(qapp, session)
    wait_until(qapp, lambda: _focus_minutes(session) == 30)
    clock.move(minutes=10)
    _end_on_widgets(window, monkeypatch)
    _settle(qapp, session)
    assert session.focus is None
    assert _focus_minutes(session) == 30


def test_just_a_timer_credits_nothing(
    qapp: QApplication,
    open_light: Callable[..., NativeWindow],
    clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, _ = _essay_at_seven(qapp, open_light, clock)
    session = window.session
    assert session.start_quick_focus() is True
    clock.move(minutes=25)
    _end_on_widgets(window, monkeypatch)
    _settle(qapp, session)
    assert session.focus is None
    assert _focus_minutes(session) == 0


def test_the_material_end_question_says_the_minutes_count_toward_the_homework(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    window, work = _essay_at_seven(qapp, open_light, clock)
    assert window.session.start_focus(work["id"], 3) is True
    show_material(qapp, window)
    window._open_focus_screen()
    pump(qapp)
    clock.move(minutes=7)
    question = window._material_page.bridge.focus.endQuestion
    assert question == "You have done 7 min of History essay. It counts toward the homework."
